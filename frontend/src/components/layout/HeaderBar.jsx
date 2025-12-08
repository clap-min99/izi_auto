import React from 'react';
import styles from './HeaderBar.module.css';
import logo from '../../assets/logo.png';

function HeaderBar({ onClickStart, onClickCoupon }) {
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
        <button className={`${styles.btn} ${styles.secondary}`} onClick={onClickCoupon}>
          쿠폰등록
        </button>
        <button className={`${styles.btn} ${styles.primary}`} onClick={onClickStart}>
          시작
        </button>
      </div>

    </header>
  );
}

export default HeaderBar;
