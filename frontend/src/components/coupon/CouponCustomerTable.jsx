import styles from './CouponCustomerTable.module.css';

function formatRemainingTime(minutes) {
  if (minutes == null) return '-';
  const hours = minutes / 60;
  return Number.isInteger(hours) ? `${hours}시간` : `${hours.toFixed(1)}시간`;
}

function formatYYMMDD(dateStr) {
  if (!dateStr) return '-';
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return '-';
  const yy = String(d.getFullYear()).slice(2);
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yy}-${mm}-${dd}`;
}

function formatPhone(value) {
  const digits = (value || '').replace(/\D/g, '').slice(0, 11); // 최대 11자리
  if (digits.length <= 3) return digits;
  if (digits.length <= 7) return `${digits.slice(0, 3)}-${digits.slice(3)}`;
  return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7)}`;
}

function toDateInputValue(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return '';
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

function minutesToHoursString(minutes) {
  if (minutes == null || minutes === '') return '';
  const h = Number(minutes) / 60;
  if (!Number.isFinite(h)) return '';
  return Number.isInteger(h) ? String(h) : String(parseFloat(h.toFixed(1)));
}



function CouponCustomerTable({
  customers,
  onClickDetail,
  onClickEdit,
  onClickDelete,

  // ✅ 인라인 편집용
  editingId,
  editForm,
  savingId,
  onChangeEdit,
  onCancelEdit,
  onSaveEdit,
}) {
  return (
    <div className={styles.wrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>No.</th>
            <th>고객이름</th>
            <th>전화번호</th>
            <th>유형</th>
            <th>등록일</th>
            <th>만료일</th>
            <th>잔여시간</th>
            <th></th>
          </tr>
        </thead>

        <tbody>
          {customers.length === 0 ? (
            <tr>
              <td colSpan={7} className={styles.empty}>등록된 고객이 없습니다.</td>
            </tr>
          ) : (
            customers.map((c, idx) => {
              const isEditing = c.id === editingId;
              const isSaving = c.id === savingId;
              const handleEditKeyDown = (e, customer) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    onSaveEdit?.(customer);
                  }
                  if (e.key === 'Escape') {
                    e.preventDefault();
                    onCancelEdit?.();
                  }
                };
              return (
                <tr key={c.id}
                className={[
                  isEditing ? styles.editingRow : '',
                  isSaving ? styles.savingRow : '',
                ].join(' ')}
                >
                  <td>{idx + 1}</td>

                  <td>
                    {isEditing ? (
                      <input
                        className={styles.editInput}
                        value={editForm.customer_name}
                        onChange={(e) => onChangeEdit?.('customer_name', e.target.value)}
                        onKeyDown={(e) => handleEditKeyDown(e, c)}
                        disabled={isSaving}
                      />
                    ) : (
                      c.customer_name
                    )}
                  </td>

                  <td>
                    {isEditing ? (
                      <input
                        className={styles.editInput}
                        value={editForm.phone_number}
                        onChange={(e) => onChangeEdit?.('phone_number', formatPhone(e.target.value))}
                        onKeyDown={(e) => handleEditKeyDown(e, c)}
                        disabled={isSaving}
                      />
                    ) : (
                      c.phone_number
                    )}
                  </td>

                  <td>{c.piano_category ?? '-'}</td>
                  <td>{formatYYMMDD(c.coupon_registered_at)}</td>
                  <td>
                    {isEditing ? (
                      <input
                        className={styles.editInput}
                        type="date"
                        value={toDateInputValue(editForm.coupon_expires_at)}
                        onChange={(e) => onChangeEdit?.('coupon_expires_at', e.target.value)}
                        onKeyDown={(e) => handleEditKeyDown(e, c)}
                        disabled={isSaving}
                      />
                    ) : (
                      formatYYMMDD(c.coupon_expires_at)
                    )}
                  </td>
                  <td>
                    {isEditing ? (
                      <input
                        className={styles.editInput}
                        inputMode="decimal"
                        type="Number"
                        step="0.1"
                        placeholder="시간"
                        value={minutesToHoursString(editForm.remaining_time)}
                        onChange={(e) => {
                          const v = e.target.value;
                          if (v === '') return onChangeEdit?.('remaining_time', '');
                          const hours = Number(v);
                          if (!Number.isFinite(hours) || hours < 0) return;
                          onChangeEdit?.('remaining_time', Math.round(hours * 60)); // ✅ 분으로 저장
                        }}
                        onKeyDown={(e) => handleEditKeyDown(e, c)}
                        disabled={isSaving}
                      />
                    ) : (
                      formatRemainingTime(c.remaining_time)
                    )}
                  </td>


                  <td>
                    <div className={styles.actionButtons}>
                      {isEditing ? (
                        <>
                          <button
                            type="button"
                            className={styles.editButton}
                            onClick={() => onSaveEdit?.(c)}
                            disabled={isSaving}
                          >
                            {isSaving ? '저장중...' : '저장'}
                          </button>
                          <button
                            type="button"
                            className={styles.deleteButton}
                            onClick={onCancelEdit}
                            disabled={isSaving}
                          >
                            취소
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            type="button"
                            className={styles.detailButton}
                            onClick={() => onClickDetail?.(c)}
                            disabled={editingId != null} // 편집 중엔 다른 행 상세 방지(선택)
                          >
                            상세
                          </button>
                          <button
                            type="button"
                            className={styles.editButton}
                            onClick={() => onClickEdit?.(c)}
                            disabled={editingId != null} // 한 번에 한 행만 편집
                          >
                            수정
                          </button>
                          <button
                            type="button"
                            className={styles.deleteButton}
                            onClick={() => onClickDelete?.(c)}
                            disabled={editingId != null}
                          >
                            삭제
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

export default CouponCustomerTable;
