"""RemoteGlobalMemory — 与 GlobalMemory 同接口的远程客户端(HTTP)。
本地 agent 用它把脱敏经验晋升到远程 global 服务,实现混合部署:
数据/推理留本地,只有脱敏模式过网络。store.promote_to_global 无需改动即可透明使用。"""
import os, json, urllib.request

class RemoteGlobalMemory:
    def __init__(self, base_url=None, token=None):
        self.base = (base_url or os.environ.get("OPENSCI_GLOBAL_URL", "http://localhost:8090")).rstrip("/")
        self.token = token or os.environ.get("OPENSCI_GLOBAL_TOKEN")
    def _post(self, path, obj):
        h={"Content-Type":"application/json"}
        if self.token: h["Authorization"]=f"Bearer {self.token}"
        req=urllib.request.Request(self.base+path, data=json.dumps(obj).encode(), headers=h, method="POST")
        return json.loads(urllib.request.urlopen(req, timeout=20).read())
    def promote(self, lesson, contributor_fp, consent):
        return self._post("/v1/global/promote", {"lesson":lesson,"contributor_fp":contributor_fp,"consent":consent})
    def query(self, kinds): return self._post("/v1/global/query", {"kinds":kinds})
    def status_for(self, signature, contributor_fp):
        r=self._post("/v1/global/status", {"signature":signature,"contributor_fp":contributor_fp})
        return None if r.get("in_global") is False else r
    def revoke(self, signature, contributor_fp):
        return self._post("/v1/global/revoke", {"signature":signature,"contributor_fp":contributor_fp})
