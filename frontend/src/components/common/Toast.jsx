import { useEffect } from "react";
import styles from "./Toast.module.css";

export default function Toast({ message, onClose, duration = 1500 }) {
  useEffect(() => {
    if (!message) return;
    const t = setTimeout(onClose, duration);
    return () => clearTimeout(t);
  }, [message, duration, onClose]);

  if (!message) return null;

  return (
    <div className={styles.toast}>
      {message}
    </div>
  );
}
