"""In-memory implementation of the guide comments contract for tests."""
import argparse, base64, hashlib, json, re, secrets, threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlencode, urlparse

MANIFEST_PATTERN = re.compile(rb'<script type="application/json" id="guide-build-manifest">(.*?)</script>', re.DOTALL)
MAX_MANIFEST = 64 * 1024
# InteropHub's hosted label pattern (GuideHtmlRules): no hyphen after the first suffix character.
HOSTED_LABEL = re.compile(r"^(?:latest|main|v[0-9]+(?:\.[0-9]+)*(?:-[A-Za-z0-9][A-Za-z0-9.]*)?)$")
DISPLAYS = ("current", "listed", "unlisted", "authors_only", "retired")
MODES = ("open", "release", "closed")
DISPOSITIONS = [{"code": "PERSUASIVE", "label": "Persuasive"}, {"code": "PERSUASIVE_MOD", "label": "Persuasive with Modification"}, {"code": "NOT_PERSUASIVE", "label": "Not Persuasive"}]

def now(): return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
def challenge(value): return base64.urlsafe_b64encode(hashlib.sha256(value.encode()).digest()).decode().rstrip("=")

class State:
    def __init__(self, origins):
        self.origins=set(origins); self.codes={}; self.tokens={}; self.comments={}; self.flags={}
        self.versions={}; self.hosted_documents={"document"}
        # Every registered guide document, hosted or not, takes build records.
        self.documents={"document","external-document"}; self.builds={}; self.next_build_id=1
        self.next_id=1; self.next_flag_id=1; self.can_view=True; self.active=True; self.lock=threading.Lock()
        # Version display and comment modes (contract 5.3.1, 5.4.1, 7.5). labels: document -> label ->
        # {"display", "commentMode", "modeSetAt"}; label_urls: document -> registered URL -> label.
        self.labels={}; self.label_urls={}

class Handler(BaseHTTPRequestHandler):
    server_version="GuideMock/2"
    @property
    def state(self): return self.server.state
    def log_message(self, *args): pass
    def cors(self):
        origin=self.headers.get("Origin")
        if origin and origin in self.state.origins:
            self.send_header("Access-Control-Allow-Origin", origin); self.send_header("Vary", "Origin"); self.send_header("Access-Control-Expose-Headers", "WWW-Authenticate")
    def json(self, status, value, extra=None):
        payload=json.dumps(value).encode(); self.send_response(status); self.cors(); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(payload)))
        for key,val in (extra or {}).items(): self.send_header(key,val)
        self.end_headers(); self.wfile.write(payload)
    def empty(self, status=204): self.send_response(status); self.cors(); self.end_headers()
    def error(self,status,code,message,field=None,current=None):
        body={"error":code,"message":message}
        if field: body["field"]=field
        if current is not None: body["current"]=current
        extra={"WWW-Authenticate":'Bearer realm="interophub", error="invalid_token"'} if status==401 else None
        self.json(status,body,extra)
    def body(self):
        try: return json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))))
        except (ValueError,json.JSONDecodeError): return None
    def refuse_origin(self):
        origin=self.headers.get("Origin")
        if origin and origin not in self.state.origins: self.error(403,"forbidden","This origin is not allowed."); return True
        return False
    def identity(self):
        auth=self.headers.get("Authorization",""); record=self.state.tokens.get(auth[7:] if auth.startswith("Bearer ") else "")
        if not record or record.get("revoked"): self.error(401,"invalid_token","The access token is invalid or expired."); return None
        return record
    def do_OPTIONS(self):
        if self.headers.get("Origin") not in self.state.origins: self.empty(403); return
        self.send_response(204); self.cors(); self.send_header("Access-Control-Allow-Methods","GET, POST, PATCH, DELETE"); self.send_header("Access-Control-Allow-Headers","Authorization, Content-Type"); self.send_header("Access-Control-Max-Age","600"); self.end_headers()
    def do_GET(self):
        p=urlparse(self.path)
        if p.path=="/home": self.sign_in(p); return
        if p.path.startswith("/test/"): self.test_control(p); return
        if self.refuse_origin(): return
        who=self.identity()
        if not who: return
        parts=p.path.strip("/").split("/"); user=who["user"]
        if len(parts)==4 and parts[:2]==["api","guide"] and parts[3]=="versions":
            self.json(200,{"versions":[dict(uploads[-1],historyCount=len(uploads),earlier=[{k:u[k] for k in ("uploadedAt","uploadedBy","sizeBytes")} for u in reversed(uploads[:-1])]) for uploads in self.state.versions.get(parts[2],{}).values()]}); return
        if len(parts)==3 and parts[:2]==["api","guide"]:
            self.json(200,{"documentKey":parts[2],"title":"Fixture guide","isActive":self.state.active,"topic":{} if self.state.can_view else None,"permissions":{"canView":self.state.can_view,"canComment":self.state.can_view and self.state.active,"isAuthor":who.get("isAuthor",False)},"user":user,"dispositions":DISPOSITIONS,"editWindowDays":14,"serverTime":now()}); return
        if len(parts)==4 and parts[:2]==["api","guide"] and parts[3]=="comments":
            if not self.state.can_view: self.error(403,"forbidden","This account cannot view comments."); return
            q=parse_qs(p.query); since=q.get("since",[None])[0]; all_states=q.get("state",[None])[0]=="all"; values=[]
            label=q.get("label",[None])[0]; page=q.get("pageUrl",[None])[0]; named=bool(label or page)
            if not label and page: label=self.resolve_label(parts[2],page)
            policy=self.policy(parts[2],label) if named else None
            author=who.get("isAuthor",False); mode=policy["commentMode"] if policy else "open"
            for item in self.state.comments.values():
                scoped=self.in_scope(item,policy)
                if policy and (mode=="closed" or (mode=="release" and not author and not scoped)): continue
                if since and item["updatedAt"]>=since: value=self.thread(item,who,True)
                elif not since and not item.get("deleted") and (all_states or item["state"] in ("OPEN","DISPOSED")): value=self.thread(item,who)
                else: continue
                # On an Open label every item is in scope (contract 5.3.1).
                if policy and not value.get("deleted"): value["inScope"]=scoped or mode=="open"
                values.append(value)
            flags=[]
            for flag in self.active_flags():
                scoped=self.in_scope(flag,policy)
                if policy and (mode=="closed" or (mode=="release" and not author and not scoped)): continue
                if policy: flag["inScope"]=scoped or mode=="open"
                flags.append(flag)
            body={"serverTime":now(),"comments":values,"reviewFlags":flags}
            if named: body["labelPolicy"]=policy
            self.json(200,body); return
        if len(parts)==4 and parts[:2]==["api","guide"] and parts[3]=="labels":
            author=who.get("isAuthor",False); rows=[]
            for name in self.known_labels(parts[2]):
                row=self.label_object(parts[2],name,author)
                if author or row["display"] not in ("authors_only","retired"): rows.append(row)
            self.json(200,{"documentKey":parts[2],"labels":rows}); return
        if len(parts)==4 and parts[:2]==["api","guide"] and parts[3]=="review-flags":
            cleared=parse_qs(p.query).get("includeCleared",["false"])[0]=="true"
            self.json(200,{"serverTime":now(),"reviewFlags":[dict(f) for f in self.state.flags.values()] if cleared else self.active_flags()}); return
        self.error(404,"not_found","Not found.")
    def sign_in(self,p):
        q=parse_qs(p.query); valid=all(q.get(k) for k in ("return_to","state","code_challenge")) and q.get("code_challenge_method")==["S256"] and q.get("response_mode")==["fragment"] and not urlparse(q["return_to"][0]).fragment
        if not valid: self.error(400,"invalid_request","The sign-in request is invalid."); return
        name=q.get("user",["Test Reader"])[0]; code=secrets.token_urlsafe(24); user={"userId":2 if name=="Test Author" else 1,"displayName":name,"organization":"Example Organization"}
        self.state.codes[code]={"challenge":q["code_challenge"][0],"returnTo":q["return_to"][0],"user":user,"isAuthor":name=="Test Author"}
        self.send_response(302); self.send_header("Location",q["return_to"][0]+"#"+urlencode({"code":code,"state":q["state"][0]})); self.end_headers()
    def do_POST(self):
        p=urlparse(self.path)
        if p.path=="/api/guide/token": self.exchange(self.body() or {}); return
        if self.refuse_origin(): return
        who=self.identity()
        if not who: return
        parts=p.path.strip("/").split("/")
        if len(parts)==5 and parts[:2]==["api","guide"] and parts[3]=="versions": self.upload_version(parts[2],parts[4],who); return
        if len(parts)==4 and parts[:2]==["api","guide"] and parts[3]=="builds": self.save_build(parts[2],who); return
        payload=self.body() or {}
        if "TEST-FIREWALL-BLOCK" in str(payload.get("text","")):
            # Stand in for a web application firewall in front of the hub: an HTML page, not the hub's JSON.
            page=b"<html><body>Request rejected.</body></html>"; self.send_response(403); self.cors(); self.send_header("Content-Type","text/html"); self.send_header("Content-Length",str(len(page))); self.end_headers(); self.wfile.write(page); return
        if len(parts)==4 and parts[:2]==["api","guide"] and parts[3]=="comments": self.add_comment(parts[2],payload,who); return
        if len(parts)==5 and parts[:3]==["api","guide","comments"] and parts[4]=="withdraw": self.withdraw(int(parts[3]),who); return
        if len(parts)==4 and parts[:2]==["api","guide"] and parts[3]=="review-flags": self.set_flag(parts[2],payload,who); return
        self.error(404,"not_found","Not found.")
    def upload_version(self,document,label,who):
        if not who.get("isAuthor"): self.error(403,"forbidden","Only an author can publish this guide."); return
        if document not in self.state.hosted_documents: self.error(409,"invalid_state","This document is not set up for hosted publishing."); return
        if not HOSTED_LABEL.fullmatch(label):
            self.error(400,"invalid_field","Choose a valid version label.","label"); return
        payload=self.rfile.read(int(self.headers.get("Content-Length","0")))
        if self.headers.get_content_type()!="text/html" or len(payload)>20*1024*1024:
            self.error(400,"invalid_field","Upload a self-contained HTML guide no larger than 20 MB.","guide"); return
        versions=self.state.versions.setdefault(document,{})
        status=200 if label in versions else 201; stamp=now()
        value={"label":label,"sizeBytes":len(payload),"uploadedBy":who["user"]["displayName"],"uploadedAt":stamp,"viewUrl":f"http://127.0.0.1:{self.server.server_port}/guide/view/{document}/{label}/"}
        versions.setdefault(label,[]).append(value); self.record_upload_manifest(document,label,payload,who,stamp); self.json(status,value)
    def record_upload_manifest(self,document,label,payload,who,stamp):
        # As the hub does: an upload is never refused over its manifest; a missing,
        # oversized, or unreadable one is recorded on the build row instead.
        match=MANIFEST_PATTERN.search(payload); record={"source":"UPLOAD","label":label,"manifest":None,"manifestError":None}
        if not match: record["manifestError"]="missing"
        elif len(match.group(1))>MAX_MANIFEST: record["manifestError"]="too_large"
        else:
            try:
                manifest=json.loads(match.group(1).decode("utf-8"))
                if not isinstance(manifest,dict) or manifest.get("schema")!=1: record["manifestError"]="unknown_schema"
                else: record["manifest"]=manifest
            except (UnicodeDecodeError,json.JSONDecodeError): record["manifestError"]="malformed"
        self.add_build(document,record,who,stamp)
    def add_build(self,document,record,who,stamp):
        ident=self.state.next_build_id; self.state.next_build_id+=1
        manifest=record.get("manifest") or {}
        row=dict(record,buildId=ident,documentKey=document,processVersion=manifest.get("processVersion"),receivedAt=stamp,receivedBy=who["user"]["displayName"])
        self.state.builds.setdefault(document,[]).append(row); return row
    def save_build(self,document,who):
        # The manifest-only contract: POST {hub}/api/guide/{documentKey}/builds.
        raw=self.rfile.read(int(self.headers.get("Content-Length","0")))
        if not who.get("isAuthor"): self.error(403,"forbidden","Only an author can publish this guide."); return
        if document not in self.state.documents: self.error(404,"not_found","Guide document not found."); return
        if not self.state.active: self.error(409,"document_inactive","This guide document is inactive."); return
        if self.headers.get_content_type()!="application/json" or len(raw)>MAX_MANIFEST+1024:
            self.error(400,"invalid_request","Send a JSON build record no larger than 64 KB."); return
        try: payload=json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError,json.JSONDecodeError): self.error(400,"invalid_request","The body is not valid JSON."); return
        manifest=payload.get("manifest") if isinstance(payload,dict) else None
        label=payload.get("label") if isinstance(payload,dict) else None
        if not isinstance(manifest,dict): self.error(400,"invalid_request","A manifest is required."); return
        if manifest.get("schema")!=1: self.error(400,"invalid_request","Unknown manifest schema."); return
        if len(json.dumps(manifest).encode("utf-8"))>MAX_MANIFEST: self.error(400,"invalid_request","The manifest is larger than 64 KB."); return
        if label is not None and (not isinstance(label,str) or len(label)>64): self.error(400,"invalid_request","The label is invalid."); return
        row=self.add_build(document,{"source":"MANIFEST","label":label,"manifest":manifest,"manifestError":None},who,now())
        self.json(201,{k:row[k] for k in ("buildId","documentKey","processVersion","receivedAt")})
    def exchange(self,payload):
        if self.refuse_origin(): return
        r=self.state.codes.get(payload.get("code")); valid=r and not r.get("used") and payload.get("returnTo")==r["returnTo"] and challenge(payload.get("codeVerifier",""))==r["challenge"]
        if not valid: self.error(400,"invalid_request","Sign-in code is invalid or expired."); return
        r["used"]=True; token="ihg_"+secrets.token_urlsafe(32)[:43]; expires=(datetime.now(timezone.utc)+timedelta(days=30)).isoformat(timespec="milliseconds").replace("+00:00","Z")
        self.state.tokens[token]={"user":r["user"],"isAuthor":r.get("isAuthor",False)}; self.json(200,{"accessToken":token,"tokenType":"Bearer","expiresAt":expires,"scopes":["comments"],"user":r["user"]})
    def written_on(self,document,payload):
        """The label a write's pageUrl resolves to, or an error already sent (contract 5.4.1)."""
        page=payload.get("pageUrl")
        if page is None: return True,None
        if not isinstance(page,str) or not page.strip() or len(page.strip())>2000: self.error(400,"invalid_field","The page address is too long.","pageUrl"); return False,None
        label=self.resolve_label(document,page.strip())
        if label and self.settings(document,label)["commentMode"]=="closed": self.error(403,"comments_closed","Comments are closed on this version."); return False,None
        return True,label
    def add_comment(self,document,payload,who):
        if not self.state.active: self.error(409,"document_inactive","This document is not accepting comments."); return
        ok,label=self.written_on(document,payload)
        if not ok: return
        text=str(payload.get("text","")).strip()
        if not text or len(text)>4000: self.error(400,"invalid_field","Comment text must be between 1 and 4,000 characters.","text"); return
        parent_id=payload.get("parentCommentId")
        if parent_id:
            parent=self.state.comments.get(parent_id)
            if not parent:
                if any(any(r["id"]==parent_id for r in t["replies"]) for t in self.state.comments.values()): self.error(400,"invalid_field","Replies cannot have replies.","parentCommentId")
                else: self.error(404,"not_found","Comment not found.")
                return
            if parent["state"] in ("CLOSED","WITHDRAWN") or parent.get("deleted"): self.error(409,"invalid_state","This thread cannot receive replies."); return
            reply=self.new_item(text,who["user"],parent_id,label); parent["replies"].append(reply); parent["updatedAt"]=reply["updatedAt"]; self.json(201,self.thread(parent,who)); return
        if not payload.get("anchor") or not isinstance(payload.get("blockIndex"),int): self.error(400,"invalid_field","An anchor and block index are required.","anchor"); return
        item=self.new_item(text,who["user"],None,label); item.update({"documentKey":document,"anchor":payload["anchor"],"blockIndex":payload["blockIndex"],"snippet":payload.get("snippet"),"state":"OPEN","disposition":None,"changeNote":None,"disposedAt":None,"disposedBy":None,"closedAt":None,"closedBy":None,"replies":[]}); self.state.comments[item["id"]]=item; self.json(201,self.thread(item,who))
    def withdraw(self,ident,who):
        found,top=self.find(ident)
        if not found: self.error(404,"not_found","Comment not found."); return
        if found["author"]["userId"]!=who["user"]["userId"] or self.expired(found): self.error(403,"edit_window_closed","The edit window has closed."); return
        if (found is top and found["state"]=="WITHDRAWN") or (found is not top and found.get("withdrawn")): self.json(200,self.thread(top,who)); return
        found["text"]=None; found["updatedAt"]=now()
        if found is top: found["state"]="WITHDRAWN"
        else: found["withdrawn"]=True; top["updatedAt"]=found["updatedAt"]
        self.json(200,self.thread(top,who))
    def do_PATCH(self):
        if self.refuse_origin(): return
        who=self.identity()
        if not who: return
        parts=urlparse(self.path).path.strip("/").split("/"); payload=self.body() or {}
        if len(parts)==5 and parts[:2]==["api","guide"] and parts[3]=="labels": self.patch_label(parts[2],unquote(parts[4]),payload,who); return
        if len(parts)!=4 or parts[:3]!=["api","guide","comments"]: self.error(404,"not_found","Not found."); return
        found,top=self.find(int(parts[3]))
        if not found or found.get("deleted"): self.error(404,"not_found","Comment not found."); return
        if payload.get("expectedUpdatedAt") is not None and payload["expectedUpdatedAt"]!=top["updatedAt"]: self.error(409,"conflict","Someone else changed this comment.",current=self.thread(top,who)); return
        allowed={"text","expectedUpdatedAt"} if found is not top else {"text","dispositionCode","changeNote","state","anchor","blockIndex","snippet","expectedUpdatedAt"}; unknown=set(payload)-allowed
        if unknown: self.error(400,"invalid_field","This field cannot be changed here.",next(iter(unknown))); return
        author_fields=set(payload)&{"dispositionCode","changeNote","state","anchor","blockIndex","snippet"}
        if author_fields and not who.get("isAuthor"): self.error(403,"forbidden","Only an author can make this change."); return
        if "text" in payload:
            if found["author"]["userId"]!=who["user"]["userId"]: self.error(403,"forbidden","Only the commenter can edit this text."); return
            if self.expired(found) or top["state"] in ("CLOSED","WITHDRAWN"): self.error(403,"edit_window_closed","The edit window has closed."); return
            text=str(payload["text"]).strip()
            if not text: self.error(400,"invalid_field","Comment text is required.","text"); return
        if "dispositionCode" in payload:
            if top["state"] in ("CLOSED","WITHDRAWN"): self.error(409,"invalid_state","This comment cannot be disposed in its current state."); return
            code=payload["dispositionCode"]
            if code is not None and code not in {d["code"] for d in DISPOSITIONS}: self.error(400,"invalid_field","Choose a valid disposition.","dispositionCode"); return
            if code is not None and not str(payload.get("changeNote",top.get("changeNote")) or "").strip(): self.error(400,"invalid_field","A change note is required when setting a disposition.","changeNote"); return
        if "changeNote" in payload and "dispositionCode" not in payload and not top.get("disposition"): self.error(400,"invalid_field","A change note requires a disposition.","changeNote"); return
        if "state" in payload:
            desired=payload["state"]
            if desired not in ("CLOSED","OPEN"): self.error(400,"invalid_field","State must be CLOSED or OPEN.","state"); return
            if (desired=="CLOSED" and top["state"] not in ("OPEN","DISPOSED")) or (desired=="OPEN" and top["state"]!="CLOSED"): self.error(409,"invalid_state","This state change is not allowed."); return
        if set(payload)&{"anchor","blockIndex","snippet"} and not payload.get("anchor"): self.error(400,"invalid_field","An anchor is required when re-attaching.","anchor"); return
        stamp=now()
        if "text" in payload: found["text"]=text; found["editedAt"]=stamp; found["updatedAt"]=stamp
        if "dispositionCode" in payload:
            code=payload["dispositionCode"]
            if code is None: top.update({"disposition":None,"changeNote":None,"state":"OPEN","disposedAt":None,"disposedBy":None})
            else: top.update({"disposition":next(d for d in DISPOSITIONS if d["code"]==code),"changeNote":str(payload.get("changeNote",top.get("changeNote"))).strip(),"state":"DISPOSED","disposedAt":stamp,"disposedBy":who["user"]})
        elif "changeNote" in payload: top["changeNote"]=str(payload["changeNote"]).strip()
        if "state" in payload:
            if payload["state"]=="CLOSED": top.update({"state":"CLOSED","closedAt":stamp,"closedBy":who["user"]})
            else: top.update({"state":"DISPOSED" if top.get("disposition") else "OPEN","closedAt":None,"closedBy":None})
        for field in ("anchor","blockIndex","snippet"):
            if field in payload: top[field]=payload[field]
        top["updatedAt"]=stamp; self.json(200,self.thread(top,who))
    def do_DELETE(self):
        if self.refuse_origin(): return
        who=self.identity()
        if not who: return
        parts=urlparse(self.path).path.strip("/").split("/")
        if parts==["api","guide","token"]: self.state.tokens[self.headers.get("Authorization","")[7:]]["revoked"]=True; self.empty(); return
        if len(parts)==4 and parts[:3]==["api","guide","comments"]:
            if not who.get("isAuthor"): self.error(403,"forbidden","Only an author can delete comments."); return
            found,top=self.find(int(parts[3]))
            if not found or found.get("deleted"): self.error(404,"not_found","Comment not found."); return
            found["deleted"]=True; found["updatedAt"]=now(); top["updatedAt"]=found["updatedAt"]
            if found is top:
                for reply in top["replies"]: reply["deleted"]=True
            self.empty(); return
        if len(parts)==5 and parts[:2]==["api","guide"] and parts[3]=="review-flags":
            if not who.get("isAuthor"): self.error(403,"forbidden","Only an author can clear review flags."); return
            flag=self.state.flags.get(int(parts[4]))
            if flag and not flag.get("clearedAt"): flag["clearedAt"]=now(); flag["clearedBy"]=who["user"]; flag["updatedAt"]=now()
            self.empty(); return
        self.error(404,"not_found","Not found.")
    def set_flag(self,document,payload,who):
        if not who.get("isAuthor"): self.error(403,"forbidden","Only an author can flag review areas."); return
        anchor=payload.get("anchor"); note=str(payload.get("note","")).strip()
        if not anchor or not note or len(note)>500: self.error(400,"invalid_field","An anchor and review note are required.","note"); return
        ok,label=self.written_on(document,payload)
        if not ok: return
        existing=next((f for f in self.state.flags.values() if f["documentKey"]==document and f["anchor"]==anchor and not f.get("clearedAt")),None); stamp=now()
        if existing: existing["note"]=note; existing["updatedAt"]=stamp; self.json(200,existing); return
        ident=self.state.next_flag_id; self.state.next_flag_id+=1; flag={"id":ident,"documentKey":document,"anchor":anchor,"note":note,"createdBy":who["user"],"createdAt":stamp,"updatedAt":stamp,"clearedAt":None,"clearedBy":None,"madeOnLabel":label}; self.state.flags[ident]=flag; self.json(201,flag)
    # ---- Labels (contract 5.3.1, 5.4.1, 7.5) ----
    def resolve_label(self,document,page):
        parsed=urlparse(page); address=f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path}"
        hosted=f"http://127.0.0.1:{self.server.server_port}/guide/view/{document}/"
        if address.startswith(hosted):
            label=address[len(hosted):].split("/")[0]
            return label if HOSTED_LABEL.fullmatch(label) else None
        best=None
        for url,label in self.state.label_urls.get(document,{}).items():
            if (address.startswith(url) or address==url.rstrip("/")) and (best is None or len(url)>len(best[0])): best=(url,label)
        return best[1] if best else None
    def known_labels(self,document):
        names=set(self.state.labels.get(document,{}))|set(self.state.versions.get(document,{}))|set(self.state.label_urls.get(document,{}).values())
        names|={b["label"] for b in self.state.builds.get(document,[]) if b.get("label")}
        dated={name:self.published_at(document,name) or "" for name in names}
        return sorted(names,key=lambda n:(0 if n=="latest" else 1 if n=="main" else 2,"".join(chr(0x10FFFF-ord(c)) for c in dated[n]) if dated[n] else "\U0010FFFF",n))
    def settings(self,document,label):
        return self.state.labels.get(document,{}).get(label) or {"display":"unlisted","commentMode":"open","modeSetAt":None}
    def published_at(self,document,label):
        uploads=self.state.versions.get(document,{}).get(label)
        if uploads: return uploads[-1]["uploadedAt"]
        builds=[b["receivedAt"] for b in self.state.builds.get(document,[]) if b.get("label")==label]
        if builds: return max(builds)
        s=self.settings(document,label)
        return s.get("modeSetAt") if s["commentMode"]=="release" else None
    def policy(self,document,label):
        if not label or label not in self.known_labels(document): return None
        s=self.settings(document,label)
        return {"label":label,"display":s["display"],"commentMode":s["commentMode"],"publishedAt":self.published_at(document,label)}
    def in_scope(self,item,policy):
        if not policy: return True
        if item.get("madeOnLabel")==policy["label"]: return True
        return bool(policy["publishedAt"]) and item["createdAt"]<policy["publishedAt"]
    def label_object(self,document,label,author):
        policy=self.policy(document,label); row=dict(policy)
        if author:
            scope=dict(policy,commentMode="release") if policy["commentMode"]!="open" else None
            row["openInScope"]=sum(1 for c in self.state.comments.values() if not c.get("deleted") and c["state"] in ("OPEN","DISPOSED") and self.in_scope(c,scope))
        return row
    def patch_label(self,document,label,payload,who):
        scopes=who.get("scopes")
        if scopes is not None and "topics:write" not in scopes: self.error(403,"insufficient_scope","This token does not allow that."); return
        if not who.get("isAuthor"): self.error(403,"forbidden","Only an editor of this topic can change labels."); return
        if not payload: self.error(400,"invalid_request","Send display or commentMode."); return
        for field,value in payload.items():
            allowed=DISPLAYS if field=="display" else MODES if field=="commentMode" else None
            if allowed is None or not isinstance(value,str) or value.lower() not in allowed: self.error(400,"invalid_field","Choose a valid value.",field); return
        if label not in self.known_labels(document): self.error(404,"not_found","Label not found."); return
        current=dict(self.settings(document,label)); demoted=None; stamp=now()
        if "display" in payload: current["display"]=payload["display"].lower()
        if "commentMode" in payload and payload["commentMode"].lower()!=current["commentMode"]: current["commentMode"]=payload["commentMode"].lower(); current["modeSetAt"]=stamp
        labels=self.state.labels.setdefault(document,{})
        if current["display"]=="current":
            for name,other in list(labels.items()):
                if name!=label and other["display"]=="current": other["display"]="listed"; demoted=name
        labels[label]=current
        self.json(200,dict(self.label_object(document,label,True),demoted=self.label_object(document,demoted,True) if demoted else None))
    def active_flags(self): return [dict(f) for f in self.state.flags.values() if not f.get("clearedAt")]
    def new_item(self,text,user,parent=None,label=None):
        ident=self.state.next_id; self.state.next_id+=1; stamp=now(); return {"id":ident,"parentId":parent,"text":text,"author":user,"madeOnLabel":label,"createdAt":stamp,"editedAt":None,"editableUntil":(datetime.now(timezone.utc)+timedelta(days=14)).isoformat(timespec="milliseconds").replace("+00:00","Z"),"updatedAt":stamp,"withdrawn":False,"deleted":False}
    def expired(self,item): return datetime.fromisoformat(item["editableUntil"].replace("Z","+00:00"))<datetime.now(timezone.utc)
    def find(self,ident):
        for top in self.state.comments.values():
            if top["id"]==ident: return top,top
            for reply in top["replies"]:
                if reply["id"]==ident: return reply,top
        return None,None
    def thread(self,item,who,tombstones=False):
        if item.get("deleted") and tombstones: return {"id":item["id"],"deleted":True,"updatedAt":item["updatedAt"]}
        result=dict(item); open_thread=item["state"] in ("OPEN","DISPOSED"); own=item["author"]["userId"]==who["user"]["userId"] and not self.expired(item) and open_thread; author=who.get("isAuthor",False)
        result["mine"]=item["author"]["userId"]==who["user"]["userId"]; result["permissions"]={"canEdit":own,"canWithdraw":own,"canReply":open_thread,"canDispose":author and open_thread,"canClose":author and item["state"] in ("OPEN","DISPOSED","CLOSED"),"canDelete":author,"canReattach":author}; result["replies"]=[]
        for reply in item["replies"]:
            if reply.get("deleted"):
                if tombstones: result["replies"].append({"id":reply["id"],"deleted":True,"updatedAt":reply["updatedAt"]})
                continue
            copy=dict(reply); copy["mine"]=reply["author"]["userId"]==who["user"]["userId"]; own_reply=reply["author"]["userId"]==who["user"]["userId"] and not self.expired(reply) and not reply.get("withdrawn") and open_thread; copy["permissions"]={"canEdit":own_reply,"canWithdraw":own_reply,"canDelete":author}; result["replies"].append(copy)
        return result
    def test_control(self,p):
        q=parse_qs(p.query); action=p.path.rsplit("/",1)[-1]
        if action=="revoke":
            token=q.get("token",[""])[0]
            if token in self.state.tokens: self.state.tokens[token]["revoked"]=True
        elif action in ("delete","close"):
            item,top=self.find(int(q.get("id",["0"])[0]))
            if item:
                if action=="delete": item["deleted"]=True
                else: top["state"]="CLOSED"
                top["updatedAt"]=now()
        elif action=="expire":
            item,_=self.find(int(q.get("id",["0"])[0]))
            if item: item["editableUntil"]="2000-01-01T00:00:00.000Z"
        elif action=="can-view": self.state.can_view=q.get("value",["true"])[0]=="true"
        elif action=="label":
            # Set a label's display and mode directly, as an author would on the settings page.
            document=q.get("document",["example-core-document"])[0]; label=q.get("label",[""])[0]
            current=dict(self.state.labels.get(document,{}).get(label) or {"display":"unlisted","commentMode":"open","modeSetAt":None})
            if "display" in q: current["display"]=q["display"][0]
            if "mode" in q: current["commentMode"]=q["mode"][0]; current["modeSetAt"]=now()
            self.state.labels.setdefault(document,{})[label]=current
        self.json(200,{"ok":True})

# People and data for trying the annotations panel against the test fixture
# (tests/fixture-project). The browser check signs in as AUTHOR and READER.
AUTHOR={"userId":9,"displayName":"Test Author","organization":"Example Organization"}
READER={"userId":10,"displayName":"Test Reader","organization":"Example Organization"}
OTHER={"userId":11,"displayName":"Dana Reviewer","organization":"Example State IIS"}

def seed_demo(state, site=None):
    """Comments, replies, and review flags on the fixture's review areas.

    With site (the static server's address, such as http://127.0.0.1:8765),
    also three labels, each a copy of the guide served under site/output/:
    guide/ is main (Open), release/ is v0.2.0 (Current, Release, published
    30 hours ago), and closed/ is v0.1.0 (Retired, Closed).
    """
    def comment(user,anchor,index,snippet,text,ago_hours,**extra):
        stamp=(datetime.now(timezone.utc)-timedelta(hours=ago_hours)).isoformat(timespec="milliseconds").replace("+00:00","Z")
        ident=state.next_id; state.next_id+=1
        item={"id":ident,"parentId":None,"text":text,"author":user,"madeOnLabel":None,"createdAt":stamp,"editedAt":None,"editableUntil":"2099-01-01T00:00:00.000Z","updatedAt":stamp,"withdrawn":False,"deleted":False,
              "documentKey":"example-core-document","anchor":anchor,"blockIndex":index,"snippet":snippet,"state":"OPEN","disposition":None,"changeNote":None,"disposedAt":None,"disposedBy":None,"closedAt":None,"closedBy":None,"replies":[]}
        item.update(extra); state.comments[ident]=item; return item
    def reply(parent,user,text,ago_hours):
        stamp=(datetime.now(timezone.utc)-timedelta(hours=ago_hours)).isoformat(timespec="milliseconds").replace("+00:00","Z")
        ident=state.next_id; state.next_id+=1
        parent["replies"].append({"id":ident,"parentId":parent["id"],"text":text,"author":user,"madeOnLabel":None,"createdAt":stamp,"editedAt":None,"editableUntil":"2099-01-01T00:00:00.000Z","updatedAt":stamp,"withdrawn":False,"deleted":False})
        parent["updatedAt"]=max(parent["updatedAt"],stamp)
    first=comment(READER,"fixture-introduction",1,"This second paragraph verifies positions within one anchor area.","Does \"position\" count list items separately, or the list as one block?",50)
    reply(first,AUTHOR,"The list is one block. I will say so in the next version.",30)
    second=comment(OTHER,"review-item",0,"A second section, with an open item for review.","Our program treats this as two items, not one. Can the guide allow for that?",26,madeOnLabel="main")
    reply(second,READER,"Same in our state.",20)
    comment(OTHER,"fx-1",0,"FX-1 A row that is a review area of its own Open","Status should be \"Proposed\" until the call decides.",12,
            state="DISPOSED",disposition=DISPOSITIONS[1],changeNote="Status column now says Proposed.",disposedAt=now(),disposedBy=AUTHOR,madeOnLabel="v0.2.0")
    comment(READER,"fixture-introduction",0,"This fixture exercises the shared build and check tools.","Typo in the first sentence (fixed already).",80,
            state="CLOSED",closedAt=now(),closedBy=AUTHOR)
    comment(OTHER,"retired-section",0,"Text from a section that was later removed.","This section contradicts chapter 3.",90)
    def flag(anchor,note,ago_hours,cleared=False):
        stamp=(datetime.now(timezone.utc)-timedelta(hours=ago_hours)).isoformat(timespec="milliseconds").replace("+00:00","Z")
        ident=state.next_flag_id; state.next_flag_id+=1
        state.flags[ident]={"id":ident,"documentKey":"example-core-document","anchor":anchor,"note":note,"createdBy":AUTHOR,"createdAt":stamp,"updatedAt":stamp,
                            "clearedAt":now() if cleared else None,"clearedBy":AUTHOR if cleared else None,"madeOnLabel":None}
    flag("fixture-introduction","Please check that the summary still matches the detail section.",40)
    flag("document-start","Old flag on the opening, cleared after the October call.",200,cleared=True)
    if site:
        document="example-core-document"; published=(datetime.now(timezone.utc)-timedelta(hours=30)).isoformat(timespec="milliseconds").replace("+00:00","Z")
        state.label_urls[document]={site+"/output/guide/":"main",site+"/output/release/":"v0.2.0",site+"/output/closed/":"v0.1.0"}
        state.labels[document]={"main":{"display":"unlisted","commentMode":"open","modeSetAt":None},
                                "v0.2.0":{"display":"current","commentMode":"release","modeSetAt":published},
                                "v0.1.0":{"display":"retired","commentMode":"closed","modeSetAt":published}}

def serve(port=0,origins=None):
    server=ThreadingHTTPServer(("127.0.0.1",port),Handler); server.state=State(origins or ["http://127.0.0.1:8765"]); return server
if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--port",type=int,default=8766); parser.add_argument("--allow-origin",action="append",default=[]); parser.add_argument("--seed-demo",action="store_true",help="Add sample comments and review flags for the test fixture."); parser.add_argument("--site",help="With --seed-demo: the static server's address, to add the main, release, and closed labels."); args=parser.parse_args(); server=serve(args.port,args.allow_origin or None)
    if args.seed_demo: seed_demo(server.state,args.site)
    print(f"Mock comments service listening on http://127.0.0.1:{server.server_port}",flush=True); server.serve_forever()
