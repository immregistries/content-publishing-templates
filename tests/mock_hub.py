"""In-memory implementation of the guide comments contract for tests."""
import argparse, base64, hashlib, json, secrets, threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

DISPOSITIONS = [{"code": "PERSUASIVE", "label": "Persuasive"}, {"code": "PERSUASIVE_MOD", "label": "Persuasive with Modification"}, {"code": "NOT_PERSUASIVE", "label": "Not Persuasive"}]

def now(): return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
def challenge(value): return base64.urlsafe_b64encode(hashlib.sha256(value.encode()).digest()).decode().rstrip("=")

class State:
    def __init__(self, origins):
        self.origins=set(origins); self.codes={}; self.tokens={}; self.comments={}; self.flags={}
        self.next_id=1; self.next_flag_id=1; self.can_view=True; self.active=True; self.lock=threading.Lock()

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
        if len(parts)==3 and parts[:2]==["api","guide"]:
            self.json(200,{"documentKey":parts[2],"title":"Fixture guide","isActive":self.state.active,"topic":{} if self.state.can_view else None,"permissions":{"canView":self.state.can_view,"canComment":self.state.can_view and self.state.active,"isAuthor":who.get("isAuthor",False)},"user":user,"dispositions":DISPOSITIONS,"editWindowDays":14,"serverTime":now()}); return
        if len(parts)==4 and parts[:2]==["api","guide"] and parts[3]=="comments":
            if not self.state.can_view: self.error(403,"forbidden","This account cannot view comments."); return
            q=parse_qs(p.query); since=q.get("since",[None])[0]; all_states=q.get("state",[None])[0]=="all"; values=[]
            for item in self.state.comments.values():
                if since and item["updatedAt"]>=since: values.append(self.thread(item,who,True))
                elif not since and not item.get("deleted") and (all_states or item["state"] in ("OPEN","DISPOSED")): values.append(self.thread(item,who))
            self.json(200,{"serverTime":now(),"comments":values,"reviewFlags":self.active_flags()}); return
        if len(parts)==4 and parts[:2]==["api","guide"] and parts[3]=="review-flags": self.json(200,{"serverTime":now(),"reviewFlags":self.active_flags()}); return
        self.error(404,"not_found","Not found.")
    def sign_in(self,p):
        q=parse_qs(p.query); valid=all(q.get(k) for k in ("return_to","state","code_challenge")) and q.get("code_challenge_method")==["S256"] and q.get("response_mode")==["fragment"] and not urlparse(q["return_to"][0]).fragment
        if not valid: self.error(400,"invalid_request","The sign-in request is invalid."); return
        name=q.get("user",["Test Reader"])[0]; code=secrets.token_urlsafe(24); user={"userId":2 if name=="Test Author" else 1,"displayName":name,"organization":"Example Organization"}
        self.state.codes[code]={"challenge":q["code_challenge"][0],"returnTo":q["return_to"][0],"user":user,"isAuthor":name=="Test Author"}
        self.send_response(302); self.send_header("Location",q["return_to"][0]+"#"+urlencode({"code":code,"state":q["state"][0]})); self.end_headers()
    def do_POST(self):
        p=urlparse(self.path); payload=self.body() or {}
        if p.path=="/api/guide/token": self.exchange(payload); return
        if self.refuse_origin(): return
        who=self.identity()
        if not who: return
        parts=p.path.strip("/").split("/")
        if len(parts)==4 and parts[:2]==["api","guide"] and parts[3]=="comments": self.add_comment(parts[2],payload,who); return
        if len(parts)==5 and parts[:3]==["api","guide","comments"] and parts[4]=="withdraw": self.withdraw(int(parts[3]),who); return
        if len(parts)==4 and parts[:2]==["api","guide"] and parts[3]=="review-flags": self.set_flag(parts[2],payload,who); return
        self.error(404,"not_found","Not found.")
    def exchange(self,payload):
        if self.refuse_origin(): return
        r=self.state.codes.get(payload.get("code")); valid=r and not r.get("used") and payload.get("returnTo")==r["returnTo"] and challenge(payload.get("codeVerifier",""))==r["challenge"]
        if not valid: self.error(400,"invalid_request","Sign-in code is invalid or expired."); return
        r["used"]=True; token="ihg_"+secrets.token_urlsafe(32)[:43]; expires=(datetime.now(timezone.utc)+timedelta(days=30)).isoformat(timespec="milliseconds").replace("+00:00","Z")
        self.state.tokens[token]={"user":r["user"],"isAuthor":r.get("isAuthor",False)}; self.json(200,{"accessToken":token,"tokenType":"Bearer","expiresAt":expires,"scopes":["comments"],"user":r["user"]})
    def add_comment(self,document,payload,who):
        if not self.state.active: self.error(409,"document_inactive","This document is not accepting comments."); return
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
            reply=self.new_item(text,who["user"],parent_id); parent["replies"].append(reply); parent["updatedAt"]=reply["updatedAt"]; self.json(201,self.thread(parent,who)); return
        if not payload.get("anchor") or not isinstance(payload.get("blockIndex"),int): self.error(400,"invalid_field","An anchor and block index are required.","anchor"); return
        item=self.new_item(text,who["user"]); item.update({"documentKey":document,"anchor":payload["anchor"],"blockIndex":payload["blockIndex"],"snippet":payload.get("snippet"),"state":"OPEN","disposition":None,"changeNote":None,"disposedAt":None,"disposedBy":None,"closedAt":None,"closedBy":None,"replies":[]}); self.state.comments[item["id"]]=item; self.json(201,self.thread(item,who))
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
        existing=next((f for f in self.state.flags.values() if f["documentKey"]==document and f["anchor"]==anchor and not f.get("clearedAt")),None); stamp=now()
        if existing: existing["note"]=note; existing["updatedAt"]=stamp; self.json(200,existing); return
        ident=self.state.next_flag_id; self.state.next_flag_id+=1; flag={"id":ident,"documentKey":document,"anchor":anchor,"note":note,"createdBy":who["user"],"createdAt":stamp,"updatedAt":stamp,"clearedAt":None,"clearedBy":None}; self.state.flags[ident]=flag; self.json(201,flag)
    def active_flags(self): return [dict(f) for f in self.state.flags.values() if not f.get("clearedAt")]
    def new_item(self,text,user,parent=None):
        ident=self.state.next_id; self.state.next_id+=1; stamp=now(); return {"id":ident,"parentId":parent,"text":text,"author":user,"createdAt":stamp,"editedAt":None,"editableUntil":(datetime.now(timezone.utc)+timedelta(days=14)).isoformat(timespec="milliseconds").replace("+00:00","Z"),"updatedAt":stamp,"withdrawn":False,"deleted":False}
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
        result["permissions"]={"canEdit":own,"canWithdraw":own,"canReply":open_thread,"canDispose":author and open_thread,"canClose":author and item["state"] in ("OPEN","DISPOSED","CLOSED"),"canDelete":author,"canReattach":author}; result["replies"]=[]
        for reply in item["replies"]:
            if reply.get("deleted"):
                if tombstones: result["replies"].append({"id":reply["id"],"deleted":True,"updatedAt":reply["updatedAt"]})
                continue
            copy=dict(reply); own_reply=reply["author"]["userId"]==who["user"]["userId"] and not self.expired(reply) and not reply.get("withdrawn") and open_thread; copy["permissions"]={"canEdit":own_reply,"canWithdraw":own_reply,"canDelete":author}; result["replies"].append(copy)
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
        self.json(200,{"ok":True})

def serve(port=0,origins=None):
    server=ThreadingHTTPServer(("127.0.0.1",port),Handler); server.state=State(origins or ["http://127.0.0.1:8765"]); return server
if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--port",type=int,default=8766); parser.add_argument("--allow-origin",action="append",default=[]); args=parser.parse_args(); server=serve(args.port,args.allow_origin or None); print(f"Mock comments service listening on http://127.0.0.1:{server.server_port}",flush=True); server.serve_forever()
