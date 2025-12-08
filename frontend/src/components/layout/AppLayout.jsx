import React from 'react';
import styles from './AppLayout.module.css';

function AppLayout({ header, content, footer }) {
  return (
    <div className={styles.root}>
      <div className={styles.frame}>
        {header}
        {content}
        {footer}
      </div>
    </div>
  );
}

export default AppLayout;
