from django.core.management.base import BaseCommand
from datetime import datetime
import os

class Command(BaseCommand):
    def handle(self, *args, **options):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 로그 파일 하나 남겨보자
        with open("scheduler_test.log", "a", encoding="utf-8") as f:
            f.write(f"[{now}] 작업 스케줄러 테스트 성공 하건슈 바보양 \n")

        self.stdout.write("scheduler test success")
