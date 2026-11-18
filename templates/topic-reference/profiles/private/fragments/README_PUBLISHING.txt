Check `hosting` in `guide.json`. With `local`, share the built guide only with
people who may see the topic. With `interophub`, the publishing workflow uploads
the guide to access-controlled version URLs. Never enable GitHub Pages; see
[INTERNAL-USE.md](INTERNAL-USE.md).

A guide is not published until InteropHub has saved its build manifest. A
hosted upload carries it. For a local guide, save it when you release with
`process/tools/publish_guide_to_hub.py output/guide/index.html --manifest-only`;
see `process/guidance/TopicReference.md`.
