# -*- mode: python ; coding: utf-8 -*-
# 검증 완료(py 3.14.5, PyInstaller 6.21.0): gspread/google.auth/google.oauth2/
# oauth2client/httplib2/certifi/pyasn1/rsa/PIL 전부 번들에 강제 포함 → 자동패치 후
# 'No module named ...' 팝업(윈도우드 부트로더 traceback 다이얼로그) 원인 제거.
# google_auth_httplib2 는 설치돼 있지 않고 gspread도 안 쓰므로 넣지 않음.
# disable_windowed_traceback 은 False 유지: True로 해도 팝업이 사라지지 않고
# (텍스트만 'Traceback is disabled...'로 바뀜) 디버깅 시 모듈명만 가려짐.
# 반드시 --clean 으로 빌드:  pyinstaller --clean squad_analyzer.spec
from PyInstaller.utils.hooks import collect_all, collect_data_files

datas = [('credentials.json.json', '.'), ('*.png', '.'), ('icon.ico', '.')]   # icon.ico: 트레이/창 아이콘이 런타임에 resource_path로 읽음
binaries = []
hiddenimports = []

# 정적분석이 놓치는 구글 시트/인증 클러스터를 통째로 수집
# anthropic: AI 밴픽 코치(v81.74) — 빠지면 'No module named anthropic' 팝업
for pkg in ('gspread', 'google.auth', 'google.oauth2', 'certifi', 'pystray', 'anthropic'):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# httplib2 는 cacerts 데이터파일을 포함(없으면 TLS 깨짐)
datas += collect_data_files('httplib2')

# 지연/문자열 임포트되는 잎 모듈(환경에 설치 확인됨)
hiddenimports += [
    'app_secrets',   # 빌드시 생성되는 비밀값 모듈(로컬/CI). 없으면 소스가 빈값으로 폴백.
    'httplib2',
    'google.auth.transport.requests',
    'google.oauth2.service_account',
    'oauth2client.service_account',
    'oauth2client.crypt',
    'oauth2client.client',
    'oauth2client._helpers',
    'pyasn1', 'pyasn1_modules', 'rsa',
    'PIL.Image', 'PIL.ImageTk',
]

hiddenimports = sorted(set(hiddenimports))

a = Analysis(
    ['squad_analyzer.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['django'],  # oauth2client.contrib.django_util 경고 억제
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# [V81.28] ONEDIR — 실행 시 임시폴더(_MEI) 추출이 없어 '업데이트 첫 실행 python DLL 로드실패' 원천 제거.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,      # 바이너리를 exe에 embed하지 않고 _internal 폴더로 분리(onedir)
    name='squad_analyzer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='squad_analyzer',      # -> dist/squad_analyzer/ (squad_analyzer.exe + _internal/)
)
