import React from 'react';

const TABS = [
  { id: 'reservation', label: '예약 관리' },
  { id: 'prepaid', label: '선불 고객' },
];

function TabBar({ activeTab, onChange }) {
  return (
    <div className="tabs">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          className={`tab ${activeTab === tab.id ? 'active' : ''}`}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export default TabBar;
