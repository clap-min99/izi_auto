// src/components/message/MessageTemplatePage.jsx
import { useEffect, useMemo, useState, useRef } from 'react';
import styles from './MessageTemplatePage.module.css';
import {
  fetchMessageTemplates,
  updateMessageTemplate,
  seedMessageTemplates,
  previewMessageTemplate,
} from '../api/messageTemplateApi';
import { fetchStudioPolicy, updateStudioPolicy } from '../api/studioPolicyApi';


const VAR_CHIPS = [
  '{studio}', '{customer_name}', '{room_name}', '{date}',
  '{start_time}', '{end_time}', '{price}',
  '{remaining_minutes}', '{duration_minutes}',
  '{piano_category}', '{room_category}',
];

function MessageTemplatePage() {
  const [templates, setTemplates] = useState([]);
  const [selectedId, setSelectedId] = useState(null);

  const selected = useMemo(
    () => templates.find((t) => t.id === selectedId) || null,
    [templates, selectedId]
  );

  const [draft, setDraft] = useState('');
  const [isActive, setIsActive] = useState(true);

  const [saving, setSaving] = useState(false);

  const [previewText, setPreviewText] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewReservationId, setPreviewReservationId] = useState('');

  const [examStart, setExamStart] = useState('');
  const [examEnd, setExamEnd] = useState('');
  const [policySaving, setPolicySaving] = useState(false);

  const hasSeededRef = useRef(false);

  const [toast, setToast] = useState({ open: false, message: '', type: 'success' });
  const showToast = (message, type = 'success') => {
  setToast({ open: true, message, type });
  window.clearTimeout(showToast._t);
  showToast._t = window.setTimeout(() => {
    setToast((prev) => ({ ...prev, open: false }));
  }, 2000);
};

  const load = async () => {
    const data = await fetchMessageTemplates();
    let list = data?.results ?? [];

    // ✅ 템플릿이 하나도 없으면 자동 seed 후 다시 로드(1회만)
    if (list.length === 0 && !hasSeededRef.current) {
      hasSeededRef.current = true;
      await seedMessageTemplates();
      const data2 = await fetchMessageTemplates();
      list = data2?.results ?? [];
    }

    setTemplates(list);

    if (list.length > 0) {
      setSelectedId((prev) => prev ?? list[0].id);
    }
    };

  const loadPolicy = async () => {
    const p = await fetchStudioPolicy();
    setExamStart(p?.exam_start_date ?? '');
    setExamEnd(p?.exam_end_date ?? '');
  };

  useEffect(() => {
      load();
      loadPolicy();
      // eslint-disable-next-line
    }, []);

  useEffect(() => {
    if (!selected) return;
    setDraft(selected.content || '');
    setIsActive(!!selected.is_active);
    setPreviewText('');
    }, [selected]); // 선택 변경 시 동기화

  const onSave = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      await updateMessageTemplate(selected.id, {
        content: draft,
        is_active: isActive,
      });
      await load();
    } finally {
      setSaving(false);
    }
  };

  const onSavePolicy = async () => {
     
    if (examStart && examEnd && examStart > examEnd) {
      showToast('❌ 시작일은 종료일보다 늦을 수 없습니다.', 'error');
      return;
    }

    setPolicySaving(true);
    try {
      await updateStudioPolicy({
        exam_start_date: examStart || null,
        exam_end_date: examEnd || null,
      });
      await loadPolicy();
      showToast('저장되었습니다.');
    } catch (e) {
      showToast(`❌ 저장 실패: ${e?.detail || e?.message || '알 수 없는 오류'}`, 'error');
    } finally {
      setPolicySaving(false);
    }
  };

  const textareaRef = useRef(null);
  const insertToken = (token) => {
  const el = textareaRef.current;

  // ref 없으면 기존처럼 뒤에 추가
  if (!el) {
    setDraft((prev) => prev + token);
    return;
  }

  const start = el.selectionStart ?? draft.length;
  const end = el.selectionEnd ?? draft.length;

  const next =
    draft.slice(0, start) +
    token +
    draft.slice(end);

  setDraft(next);

  // 렌더 후 커서 위치 복구
  requestAnimationFrame(() => {
    el.focus();
    const pos = start + token.length;
    el.setSelectionRange(pos, pos);
  });
};


  const onPreview = async () => {
    if (!selected) return;
    setPreviewLoading(true);
    try {
        const rid = previewReservationId ? Number(previewReservationId) : null;
        const data = await previewMessageTemplate(selected.code, Number.isFinite(rid) ? rid : null);
        setPreviewText(data?.rendered ?? ''); 
    } finally {
        setPreviewLoading(false);
    }
    };

  return (
    <div className={styles.container}>
      {/* 좌측 리스트 */}
      <div className={styles.left}>
  {/* 상단 고정 헤더 */}
  <div className={styles.leftHeader}>
    <div className={styles.leftTitle}>💬 문자 템플릿</div>
  </div>

  {/* ✅ 가운데: 템플릿 리스트만 스크롤 */}
  <div className={styles.templateListScroll}>
    <div className={styles.templateList}>
      {templates.map((t) => {
        const active = t.id === selectedId;
        return (
          <button
            key={t.id}
            type="button"
            className={[styles.templateItem, active ? styles.templateItemActive : ''].join(' ')}
            onClick={() => setSelectedId(t.id)}
          >
            <div className={styles.itemTop}>
              <span className={styles.itemTitle}>{t.title}</span>
              <span className={[styles.badge, t.is_active ? styles.badgeOn : styles.badgeOff].join(' ')}>
                {t.is_active ? '사용' : '미사용'}
              </span>
            </div>
            <div className={styles.itemCode}>{t.code}</div>
          </button>
        );
      })}

      {templates.length === 0 && (
        <div className={styles.emptyBox}>
          템플릿이 없습니다.
        </div>
      )}
    </div>
  </div>

  {/* ✅ 하단 고정: 입시기간 설정 */}
  <div className={styles.policyDock}>
    <div className={styles.policyTitle}>입시기간</div>

    <div className={styles.policyRow}>
      <div className={styles.policyField}>
        <div className={styles.policyLabel}>시작일</div>
        <input
          type="date"
          className={styles.policyInput}
          value={examStart}
          onChange={(e) => setExamStart(e.target.value)}
        />
      </div>

      <div className={styles.policyField}>
        <div className={styles.policyLabel}>종료일</div>
        <input
          type="date"
          className={styles.policyInput}
          value={examEnd}
          onChange={(e) => setExamEnd(e.target.value)}
        />
      </div>
    </div>

    <button
      type="button"
      className={styles.secondaryButton}
      onClick={onSavePolicy}
      disabled={policySaving}
      style={{ width: '100%', marginTop: 10 }}
    >
      {policySaving ? '저장중...' : '기간 저장'}
    </button>

    
  </div>
</div>
            
          

      {/* 우측 편집 */}
      <div className={styles.right}>
        {!selected ? (
          <div className={styles.emptyRight}>좌측에서 템플릿을 선택해주세요.</div>
        ) : (
          <>
            <div className={styles.headerRow}>
              <div>
                <div className={styles.pageTitle}>{selected.title}</div>
                <div className={styles.subText}>{selected.code}</div>
              </div>
              <label className={styles.toggle}>
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                />
                <span>사용</span>
              </label>
            </div>
            

            <div className={styles.chips}>
              {VAR_CHIPS.map((v) => (
                <button
                  key={v}
                  type="button"
                  className={styles.chip}
                  onClick={() => insertToken(v)}
                >
                  {v}
                </button>
              ))}
            </div>

            <textarea
              ref={textareaRef}
              className={styles.textarea}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              rows={10}
              placeholder="문자 내용을 입력하세요"
            />

            <div className={styles.actionRow}>
              <button
                type="button"
                className={styles.primaryButton}
                onClick={onSave}
                disabled={saving}
              >
                {saving ? '저장중...' : '저장'}
              </button>

              <div className={styles.previewBox}>
                <input
                  className={styles.previewInput}
                  value={previewReservationId}
                  onChange={(e) => setPreviewReservationId(e.target.value)}
                  placeholder="미리보기 예약 ID(선택)"
                />
                <button
                  type="button"
                  className={styles.secondaryButton}
                  onClick={onPreview}
                  disabled={previewLoading}
                >
                  {previewLoading ? '미리보기...' : '미리보기'}
                </button>
              </div>
            </div>

            {previewText && (
              <div className={styles.previewResult}>
                <div className={styles.previewTitle}>미리보기 결과</div>
                <pre className={styles.previewPre}>{previewText}</pre>
              </div>
            )}
          </>
            )}
            {toast.open && (
              <div className={[styles.toast, toast.type === 'error' ? styles.toastError : styles.toastSuccess].join(' ')}>
                {toast.message}
              </div>
            )}
      </div>
    </div>
  );
}

export default MessageTemplatePage;
