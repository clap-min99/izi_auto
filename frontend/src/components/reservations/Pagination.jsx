// Pagination.jsx
import React, { useMemo } from "react";
import styles from "./Pagination.module.css";

function Pagination({ currentPage, totalPages, onChange, windowSize = 5 }) {
  const { pages, showLeftEllipsis, showRightEllipsis, startPage, endPage } =
    useMemo(() => {
      const size = Math.max(3, windowSize); // 최소 3
      const half = Math.floor(size / 2);

      let start = Math.max(1, currentPage - half);
      let end = Math.min(totalPages, start + size - 1);

      // end가 먼저 닿았으면 start를 다시 당김
      start = Math.max(1, end - size + 1);

      const pageList = [];
      for (let p = start; p <= end; p++) pageList.push(p);

      return {
        pages: pageList,
        startPage: start,
        endPage: end,
        showLeftEllipsis: start > 2,            // 1, ... 사이
        showRightEllipsis: end < totalPages - 1 // ..., totalPages 사이
      };
    }, [currentPage, totalPages, windowSize]);

  const go = (p) => {
    if (p < 1 || p > totalPages || p === currentPage) return;
    onChange(p);
  };

  return (
    <div className={styles.pagination}>
      {/* 처음 */}
      <button
        className={styles.navBtn}
        onClick={() => go(1)}
        disabled={currentPage === 1}
      >
        «
      </button>

      {/* 이전 */}
      <button
        className={styles.navBtn}
        onClick={() => go(currentPage - 1)}
        disabled={currentPage === 1}
      >
        ‹
      </button>

      {/* 1 페이지 */}
      {startPage > 1 && (
        <button
          className={`${styles.pageBtn} ${currentPage === 1 ? styles.active : ""}`}
          onClick={() => go(1)}
        >
          1
        </button>
      )}

      {/* 왼쪽 ... */}
      {showLeftEllipsis && <span className={styles.ellipsis}>…</span>}

      {/* 중앙 window */}
      {pages.map((page) => (
        <button
          key={page}
          className={`${styles.pageBtn} ${currentPage === page ? styles.active : ""}`}
          onClick={() => go(page)}
        >
          {page}
        </button>
      ))}

      {/* 오른쪽 ... */}
      {showRightEllipsis && <span className={styles.ellipsis}>…</span>}

      {/* 마지막 페이지 */}
      {endPage < totalPages && (
        <button
          className={`${styles.pageBtn} ${
            currentPage === totalPages ? styles.active : ""
          }`}
          onClick={() => go(totalPages)}
        >
          {totalPages}
        </button>
      )}

      {/* 다음 */}
      <button
        className={styles.navBtn}
        onClick={() => go(currentPage + 1)}
        disabled={currentPage === totalPages}
      >
        ›
      </button>

      {/* 끝 */}
      <button
        className={styles.navBtn}
        onClick={() => go(totalPages)}
        disabled={currentPage === totalPages}
      >
        »
      </button>
    </div>
  );
}

export default Pagination;
