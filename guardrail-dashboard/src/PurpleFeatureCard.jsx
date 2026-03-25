// PurpleFeatureCard.jsx
import React from 'react';

const PurpleFeatureCard = ({ title, description, buttonText, children, className }) => {
  return (
    // Removed fixed h/w, added h-full w-full so it fills the grid cell
    <div className={`h-full w-full border-2 border-[rgba(75,30,133,0.5)] rounded-[1.5em] bg-gradient-to-br from-[rgba(75,30,133,0.8)] to-[rgba(75,30,133,0.01)] text-white font-nunito p-[1.5em] flex flex-col gap-[1em] backdrop-blur-[12px] shadow-2xl ${className || ''}`}>
      
      {/* HEADER SECTION */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-[1.5em] font-medium tracking-wide">{title}</h1>
          {description && (
            <p className="text-[0.85em] text-slate-300 mt-1">
              {description}
            </p>
          )}
        </div>
        
        {/* OPTIONAL BUTTON (Only renders if buttonText is provided) */}
        {buttonText && (
          <button className="h-fit w-fit px-[1em] py-[0.4em] text-sm border-[1px] border-[rgba(168,85,247,0.4)] rounded-full flex justify-center items-center gap-[0.5em] overflow-hidden group hover:translate-y-[0.125em] hover:bg-[rgba(75,30,133,0.5)] transition-all duration-200 backdrop-blur-[12px]">
            <p>{buttonText}</p>
            <svg className="w-5 h-5 group-hover:translate-x-[20%] duration-300" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" strokeLinejoin="round" strokeLinecap="round" />
            </svg>
          </button>
        )}
      </div>

      {/* CONTENT SECTION (Where the charts/maps go) */}
      <div className="flex-grow w-full relative">
        {children}
      </div>
    </div>
  );
}

export default PurpleFeatureCard;