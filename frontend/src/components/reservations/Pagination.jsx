import React from 'react';

function Pagination({ currentPage = 1, totalPages = 5, onChange }) {
  const pages = Array.from({ length: totalPages }, (_, i) => i + 1);

  return (
    <footer className="pagination">
      {pages.map((p) => (
        <button
          key={p}
          className={`page-btn ${p === currentPage ? 'active' : ''}`}
          onClick={() => onChange && onChange(p)}
        >
          {p}
        </button>
      ))}
    </footer>
  );
}

export default Pagination;
