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


def pytest_runtest_logreport(report):
    """يكتب سبب الفشل فوراً: إن توقف Python بعده (نوافذ Qt على Windows) لا يضيع الملخص النهائي."""
    if report.failed:
        import sys
        print(f"\n===== فشل {report.nodeid} =====\n{report.longreprtext[-4000:]}\n", file=sys.__stderr__, flush=True)
