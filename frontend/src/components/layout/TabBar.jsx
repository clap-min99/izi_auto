import React from 'react';
import styles from './TabBar.module.css';


function TabBar({ activeTab, onChange, rightContent }) {
  const TABS = [
    { id: 'reservation', label: '예약 관리' },
    { id: 'prepaid', label: '쿠폰 고객' },
    { id: 'deposit', label: '계좌 확인' },
    { id: 'message', label: '문자 관리' },
    { id: 'send_sms', label: '쿠폰 문자' },
  ];

  return (
    <div className={styles.tabRow}>
      <div className={styles.tabs}>
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={`${styles.tab} ${activeTab === tab.id ? styles.active : ''}`}
            onClick={() => onChange(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className={styles.rightArea}>{rightContent}</div>
    </div>
  );
}


export default TabBar;
