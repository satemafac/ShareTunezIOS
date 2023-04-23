import React from 'react';
import './Modal.css';

const Modal = ({ children, onClose }) => {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        {children}
        <button className="modal-close-btn" onClick={onClose}>
          <span className="material-icons">close</span>
        </button>
      </div>
    </div>
  );
};

export default Modal;
