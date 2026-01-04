import { useState } from "react";
import Toast from "../common/Toast";
import styles from "./SendSMSPage.module.css";
import { sendBulkCouponSMS } from "../api/smsApi";

export default function SendSMSPage() {
  const [message, setMessage] = useState("");
  const [category, setCategory] = useState("국산");
  const [toast, setToast] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    const ok = window.confirm(
      `${category} 쿠폰 이용자에게 문자를 보내시겠습니까?`
    );
    if (!ok) return;

    setLoading(true);
    try {
      await sendBulkCouponSMS({ category, message });
      setToast("전송되었습니다.");
      setMessage("");
    } catch (e) {
      setToast(e?.message || "문자 전송 실패");
    } finally {
      setLoading(false);
    }
  };
  return (
    <div className={styles.container}>
      <h1 className={styles.title}> 쿠폰 사용자 문자 전송</h1>

      <div className={styles.field}>
        <label className={styles.label}>대상 그룹</label>
        <select
          className={styles.select}
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          <option value="국산">국산 쿠폰 사용자</option>
          <option value="수입">수입 쿠폰 사용자</option>
        </select>
      </div>

      <div className={styles.field}>
        <label className={styles.label}>보낼 메시지</label>
        <textarea
          rows={6}
          className={styles.textarea}
        //   placeholder="예: 방 비밀번호가 변경되었습니다."
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />
      </div>

      <div className={styles.actions}>
        <button
          onClick={handleSend}
          disabled={loading || !message.trim()}
          className={styles.sendButton}
        >
          {loading ? "전송 중..." : "📨 보내기"}
        </button>
      </div>

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
