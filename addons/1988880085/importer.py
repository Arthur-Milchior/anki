from anki.importing.anki2 import Anki2Importer


def _mid(self, srcMid):
    "Return local id for remote MID."
    # already processed this mid?
    if srcMid in self._modelMap:
        return self._modelMap[srcMid]
    mid = srcMid
    srcModel = self.src.models.get(srcMid)
    srcScm = self.src.models.scmhash(srcModel)
    while True:
        # missing from target col?
        if not self.dst.models.have(mid):
            # copy it over
            model = srcModel.copy()
            model['id'] = mid
            model['usn'] = self.col.usn()
            model['ls'] = self.col.ls
            self.dst.models.update(model)
            break
        # there's an existing model; do the schemas match?
        dstModel = self.dst.models.get(mid)
        dstScm = self.dst.models.scmhash(dstModel)
        if srcScm == dstScm:
            # copy styling changes over if newer
            if srcModel['mod'] > dstModel['mod']:
                model = srcModel.copy()
                model['id'] = mid
                model['usn'] = self.col.usn()
                self.dst.models.update(model)
            break
        # as they don't match, try next id
        mid += 1
    # save map and return new mid
    self._modelMap[srcMid] = mid
    return mid
Anki2Importer._mid = _mid
