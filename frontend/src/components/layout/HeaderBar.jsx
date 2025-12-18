import React from 'react';
import { useState } from "react";
import styles from './HeaderBar.module.css';
import logo from '../../assets/logo.png';

function HeaderBar({ automationEnabled, automationLoaded, onToggleAutomation, onClickCoupon, onClickRoomPw }) {
  return (
    <header className={styles.header}>
      
      {/* 로고 영역 */}
      <div className={styles.logoArea}>
        <div className={styles.logoRow}>
          <img src={logo} alt="logo" className={styles.logoImage} />
          <div className={styles.title}>이지피아노스튜디오 예약관리</div>
        </div>
      </div>

      {/* 오른쪽 버튼 영역 */}
      <div className={styles.headerButtons}>
        {/* ✅ 자동화 상태 라벨 (작은 배지) */}
        {automationLoaded && (
          <div
            className={`${styles.automationBadge} ${
              automationEnabled ? styles.badgeOn : styles.badgeOff
            }`}
          >
            <span>
              {automationEnabled ? '자동화 실행 중' : '일시 정지'}
            </span>
            <span
              className={`${styles.statusDot} ${
                automationEnabled ? styles.dotOn : styles.dotOff
              }`}
            />
          </div>
        )}

        {/* 기존 버튼들 */}
        <div className={styles.buttonRow}>
          <button
            className={`${styles.btn} ${styles.secondary}`}
            onClick={onClickRoomPw}
          >
            방 비밀번호
          </button>

          <button
            className={`${styles.btn} ${styles.secondary}`}
            onClick={onClickCoupon}
          >
            쿠폰등록
          </button>

          {/* 토글 */}
          <div
            className={`${styles.toggleWrapper} ${
              automationEnabled ? styles.on : styles.off
            } ${!automationLoaded ? styles.disabled : ''}`}
            onClick={automationLoaded ? onToggleAutomation : undefined}
          >
            <span
              className={`${styles.toggleText} ${
                automationEnabled ? styles.textOn : styles.textOff
              }`}
            >
              {automationEnabled ? 'ON' : 'OFF'}
            </span>
            <div className={styles.toggleThumb} />
          </div>
        </div>
      </div>
    </header>
  );
}


export default HeaderBar;
