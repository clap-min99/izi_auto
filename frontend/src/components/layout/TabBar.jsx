import React from 'react';
import styles from './TabBar.module.css';

const TABS = [
  { id: 'reservation', label: '예약 관리' },
  { id: 'prepaid', label: '선불 고객' },
];

function TabBar({ activeTab, onChange }) {
  return (
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
  );
}

export default TabBar;
