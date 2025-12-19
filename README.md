# IZI 프로젝트

### 프로젝트 시작하기

- 가상환경 설정

    1. venv 만들기
        
        `python -m venv venv`

    2. 가상 환경 on

        `source venv/Scripts/activate`
    
    3. 가상환경에 필요한 패키지 저장

        `pip freeze > requirements.txt`
    
    4. 저장해놓은 패키지 설치(다른 사람이 설치한 패키지 받기 or 다른 환경에서 새로 시작할 때)

        `pip install -r requirements.txt`
    
    5. 가상환경 off

        `deactivate`

---

### 프론트엔드(react)
    
- 프로젝트 생성(25/12/07) 

    1. 프론트엔드 폴더 생성

        `npm create vite@latest frontend -- --template react`

    2. 프론트엔드 폴더 이동 후 실행

        ```
        cd frontend
        npm install 
        npm run dev
        ```

---

### 백엔드(django)

- 프로젝트 생성(25/12/07)

    1. 백엔드 폴더 생성

        루트 폴더에 백엔드 폴더 생성하기

        `mkdir backend`

    2. 백엔드 프로젝트 생성 

        `django-admin startproject projectname .`
    
    3. 백엔드 앱 생성

        `python manage.py startapp apps(앱이름)`

    4. 앱 생성 후 settings.py에 등록

        ```py
        INSTALLED_APPS = [
        'apps',
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        ]
        ```
    
    5. 마이그레이션 생성 & DB적용

        ```
        python manage.py makemigrations
        python manage.py migrate
        ```
        SQLite DB(db.sqlite3)가 만들어짐

    6. django 서버 켜기

        `python manage.py runserver`


---

### electron

- 뼈대잡기(25/12/07)

    1. 루트파일에 electron 폴더 생성

        `mkdir electron`

    2. electron 설치

        ```
        npm init -y
        npm install electron --save-dev
        ```

    3. electron에 main.js 설정
    
        ```javascript
        const { app, BrowserWindow } = require('electron');
        const path = require('path');

        function createWindow() {
        const win = new BrowserWindow({
            width: 1200,
            height: 800,
            webPreferences: {
            // 나중에 preload, contextIsolation 설정할 예정
            },
        });

        // 지금은 일단 React dev 서버 띄운다는 가정
        win.loadURL('http://127.0.0.1:5173'); // 나중에 빌드 파일로 변경 가능
        }

        app.whenReady().then(() => {
        createWindow();

        app.on('activate', () => {
            if (BrowserWindow.getAllWindows().length === 0) createWindow();
        });
        });

        app.on('window-all-closed', () => {
        if (process.platform !== 'darwin') app.quit();
        });
        ```
    4. electron/package.json 수정

        ```js
        "scripts": {
        "start": "electron ."
        }
        ```
        위와 같이 변경
    
    5. electron 폴더에서 
     
        `npm run start` 실행

        React dev 서버가 떠 있을 때 Electron 창에 React 화면이 뜬다
        (리액트 서버 켜고 일렉트론 실행)

---
## clone 받고 할 일 
1. 가상환경 설치

2. 가상환경 켜기

3. pip install -r requirements.txt

4. frontend 폴더 -> npm install 

5. electron 폴더 -> npm install electron

6. .env 넣기

---
## 작업 스케쥴러 사용법
1. [일반] 탭
    - 이름 : ex.알림톡 보내기
    - 설명 : 알림톡 실행 파일
    - 사용자가 로그온되어 있지 않아도 실행됨. 가장 높은 권한으로 실행
2. [트리커] 탭
    - 새로만들기 ... 클릭
    - 설정
        - 시작: 예약
        - 설정: 주기 정하기
        - 시작날짜/시간
    - 사용 체크 
    - 확인
3. [동작] 탭 -> 무엇을 실행하는지
    - 새로 만들기 ...
    - 동작: 프로그램 시작
    - 프로그램/스크립트
        - 가상환경 python 경로: `C:\dev\izi_auto\venv\Scripts\python.exe` 
        - 인수 추가: `manage.py test_scheduler`
        - 시작 위치: `C:\dev\izi_auto\backend` (파일 위치에 따라 바꾸기, manage.py 위치한 폴더)
    - 확인
4. [조건] 탭
    - 컴퓨터가 AC 전원일 때만 시작 -> 체크 헤제
    - 예약된 시간에 컴퓨터를 깨움 -> 체크
5. [설정] 탭
    - 예약된 시작을 놓치면 가능한 빨리 실행
    - 실패하면 다시 시작
        - 간격: 1분
        - 시도횟수: 3회
6. [확인] -> 비밀번호 입력 -> 저장
7. 등록확인
    작업 스케줄러 라이브러리 클릭 
    가운데 목록에 알림톡 테스트, 다음 실행시간, 상태->준비 확인하기


* 운영중 쿠폰 이력 문자 보내고 싶을 때
 위 방법대로 하되, 
 
 프로그램/스크립트: C:{폴더위치}\izi_auto\venv\Scripts\python.exe
 
 시작위치: C:{폴더위치}\izi_auto\backend
 
 인수에 `manage.py send_coupon_usage_sms --send` 넣으면 실제로 발송됨
