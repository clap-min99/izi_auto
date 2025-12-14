// src/components/message/MessageTemplatePage.jsx
import { useEffect, useMemo, useState, useRef } from 'react';
import styles from './MessageTemplatePage.module.css';
import {
  fetchMessageTemplates,
  updateMessageTemplate,
  seedMessageTemplates,
  previewMessageTemplate,
} from '../api/messageTemplateApi';

const VAR_CHIPS = [
  '{studio}', '{customer_name}', '{room_name}', '{date}',
  '{start_time}', '{end_time}', '{price}',
  '{remaining_minutes}', '{duration_minutes}',
  '{coupon_category}', '{room_category}', '{alt_times}',
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

  const hasSeededRef = useRef(false);

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

  useEffect(() => {
    load();
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

  const insertToken = (token) => setDraft((prev) => prev + token);

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
        <div className={styles.leftHeader}>
          <div className={styles.leftTitle}>문자 템플릿</div>
        </div>

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
              템플릿이 없습니다. ‘기본값 생성’을 눌러주세요.
            </div>
          )}
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
      </div>
    </div>
  );
}

export default MessageTemplatePage;
