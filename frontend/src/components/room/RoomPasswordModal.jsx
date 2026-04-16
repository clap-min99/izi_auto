import React, { useEffect, useMemo, useState } from "react";
import styles from "./RoomPasswordModal.module.css";
import {
  fetchRoomPasswords,
  createRoomPassword,
  updateRoomPassword,
} from "../api/roomPasswordApi";

const ROOM_LIST = [
  { room_number: 1, room_name: "Room1_야마하 그랜드" },
  { room_number: 2, room_name: "Room2_삼익 그랜드" },
  { room_number: 3, room_name: "Room3_야마하 그랜드" },
  { room_number: 4, room_name: "Room4_삼익 그랜드" },
  { room_number: 5, room_name: "Room5_가와이 그랜드" },
  { room_number: 6, room_name: "Room6_영창 그랜드" },
];

export default function RoomPasswordModal({ open, onClose, onSaved }) {
  const [rows, setRows] = useState([]); 
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // 🔥 room_number 기준 매핑
  const roomMap = useMemo(() => {
    const m = new Map();
    rows.forEach((r) => m.set(r.room_number, r));
    return m;
  }, [rows]);

  useEffect(() => {
    if (!open) return;

    setError("");
    setLoading(true);

    fetchRoomPasswords()
      .then((data) => {
        const list = Array.isArray(data) ? data : data?.results ?? [];

        // 🔥 room_number 기준
        const byNumber = new Map(list.map((x) => [x.room_number, x]));

        const merged = ROOM_LIST.map((room) => {
          const found = byNumber.get(room.room_number);

          return {
            room_number: room.room_number,
            room_name: room.room_name,
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

  // 🔥 room_number 기준 변경
  const handleChange = (roomNumber, value) => {
    setRows((prev) =>
      prev.map((r) =>
        r.room_number === roomNumber ? { ...r, room_pw: value } : r
      )
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
          const created = await createRoomPassword({
            room_name: r.room_name,
            room_number: r.room_number, // 🔥 명시적으로 전달 (안정성 ↑)
            room_pw: pw,
          });

          if (created?.id) {
            setRows((prev) =>
              prev.map((x) =>
                x.room_number === r.room_number
                  ? { ...x, id: created.id }
                  : x
              )
            );
          }
        }
      }

      onSaved?.("저장되었습니다");
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
          <button className={styles.closeBtn} onClick={onClose}>
            ✕
          </button>
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

                {ROOM_LIST.map((room) => {
                  const r = roomMap.get(room.room_number) ?? {
                    room_number: room.room_number,
                    room_name: room.room_name,
                    room_pw: "",
                  };

                  return (
                    <div key={room.room_number} className={styles.row}>
                      <div className={styles.colRoom}>
                        <input
                          className={styles.readonly}
                          value={room.room_name}
                          readOnly
                        />
                      </div>
                      <div className={styles.colPw}>
                        <input
                          className={styles.input}
                          value={r.room_pw ?? ""}
                          onChange={(e) =>
                            handleChange(room.room_number, e.target.value)
                          }
                          placeholder="비밀번호 입력"
                        />
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className={styles.hint}>
                문자 템플릿에서 <b>{"{room_pw}"}</b> 변수를 사용하면 룸에 맞는
                비밀번호가 자동으로 들어가요.
              </div>
            </>
          )}
        </div>

        <div className={styles.footer}>
          <button
            className={styles.secondaryBtn}
            onClick={onClose}
            disabled={saving}
          >
            닫기
          </button>
          <button
            className={styles.primaryBtn}
            onClick={handleSaveAll}
            disabled={saving || loading}
          >
            {saving ? "저장 중..." : "저장"}
          </button>
        </div>
      </div>
    </div>
  );
}