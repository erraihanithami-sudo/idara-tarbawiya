"""أدوات مشتركة للاختبارات. كل البيانات وهمية."""

import pytest

from idara.data.db import ouvrir_base
from idara.data.dossier import DossierDonnees


@pytest.fixture
def dossier(tmp_path):
    # اسم عربي بمسافة عمداً: نفس ما سيختاره المدير على Windows
    return DossierDonnees(tmp_path / "الإدارة التربوية").preparer()


@pytest.fixture
def conn(dossier):
    c = ouvrir_base(dossier.base)
    yield c
    c.close()
