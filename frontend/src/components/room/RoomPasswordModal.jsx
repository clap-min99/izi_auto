import React, { useEffect, useMemo, useState } from "react";
import styles from "./RoomPasswordModal.module.css";
import { fetchRoomPasswords, createRoomPassword, updateRoomPassword } from "../api/roomPasswordApi";

const ROOM_LIST = [
  "Room1_야마하 그랜드",
  "Room2_삼익 그랜드",
  "Room3_야마하 그랜드",
  "Room4_삼익 그랜드",
  "Room5_가와이 그랜드",
  "Room6_영창 그랜드",
];

export default function RoomPasswordModal({ open, onClose }) {
  const [rows, setRows] = useState([]); // { room_name, room_pw, id? }
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const roomMap = useMemo(() => {
    const m = new Map();
    rows.forEach((r) => m.set(r.room_name, r));
    return m;
  }, [rows]);

  useEffect(() => {
    if (!open) return;

    setError("");
    setLoading(true);

    fetchRoomPasswords()
      .then((data) => {
        // DRF pagination 켜져있으면 data.results, 아니면 data
        const list = Array.isArray(data) ? data : (data?.results ?? []);
        const byName = new Map(list.map((x) => [x.room_name, x]));

        const merged = ROOM_LIST.map((name) => {
          const found = byName.get(name);
          return {
            room_name: name,
            room_pw: found?.room_pw ?? "",
            id: found?.id ?? null,
          };
        });

        setRows(merged);
      })
      .catch((e) => {
        setError(e?.message ?? "불러오기 실패");
      })
      .finally(() => setLoading(false));
  }, [open]);

  const handleChange = (roomName, value) => {
    setRows((prev) =>
      prev.map((r) => (r.room_name === roomName ? { ...r, room_pw: value } : r))
    );
  };

  const handleSaveAll = async () => {
    setSaving(true);
    setError("");

    try {
      for (const r of rows) {
        const pw = (r.room_pw ?? "").trim();

        if (r.id) {
          await updateRoomPassword(r.id, { room_pw: pw });
        } else {
          // DB에 없던 방이면 생성(upsert)
          const created = await createRoomPassword({ room_name: r.room_name, room_pw: pw });
          // created가 결과 객체면 id 반영
          if (created?.id) {
            setRows((prev) =>
              prev.map((x) => (x.room_name === r.room_name ? { ...x, id: created.id } : x))
            );
          }
        }
      }
      onClose();
    } catch (e) {
      setError(e?.message ?? "저장 실패");
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  return (
    <div className={styles.backdrop} onMouseDown={onClose}>
      <div className={styles.modal} onMouseDown={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <div className={styles.title}>방 비밀번호 설정</div>
          <button className={styles.closeBtn} onClick={onClose}>✕</button>
        </div>

        <div className={styles.body}>
          {loading ? (
            <div className={styles.info}>불러오는 중...</div>
          ) : (
            <>
              {error && <div className={styles.error}>{error}</div>}

              <div className={styles.table}>
                <div className={`${styles.row} ${styles.head}`}>
                  <div className={styles.colRoom}>룸명</div>
                  <div className={styles.colPw}>비밀번호</div>
                </div>

                {ROOM_LIST.map((roomName) => {
                  const r = roomMap.get(roomName) ?? { room_name: roomName, room_pw: "" };

                  return (
                    <div key={roomName} className={styles.row}>
                      <div className={styles.colRoom}>
                        <input className={styles.readonly} value={roomName} readOnly />
                      </div>
                      <div className={styles.colPw}>
                        <input
                          className={styles.input}
                          value={r.room_pw ?? ""}
                          onChange={(e) => handleChange(roomName, e.target.value)}
                          placeholder="비밀번호 입력"
                        />
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className={styles.hint}>
                문자 템플릿에서 <b>{"{room_pw}"}</b> 변수를 사용하면 룸명에 맞는 비밀번호가 자동으로 들어가요.
              </div>
            </>
          )}
        </div>

        <div className={styles.footer}>
          <button className={styles.secondaryBtn} onClick={onClose} disabled={saving}>
            닫기
          </button>
          <button className={styles.primaryBtn} onClick={handleSaveAll} disabled={saving || loading}>
            {saving ? "저장 중..." : "저장"}
          </button>
        </div>
      </div>
    </div>
  );
}
