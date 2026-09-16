import React from 'react';

const TopBar: React.FC = () => {
  return (
    <header
      className="h-16 px-8 flex items-center justify-between border-b border-white/[0.04] bg-[#0c0d12] flex-shrink-0 z-20"
      data-purpose="top-navigation-bar"
    >
      {/* Search Bar */}
      <div className="relative w-72">
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-500">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path
              d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <input
          className="w-full pl-9 pr-4 py-1.5 bg-[#171920] border border-white/5 rounded-full text-sm text-gray-300 placeholder-gray-500 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/30 transition"
          placeholder="Search"
          type="text"
        />
      </div>

      {/* Right Header Actions */}
      <div className="flex items-center gap-4">
        {/* Notification Bell */}
        <button
          aria-label="Notifications"
          className="relative p-2 text-gray-400 hover:text-white rounded-full hover:bg-white/5 transition"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
            <path
              d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          {/* Active Notification Indicator Dot */}
          <span className="absolute top-2 right-2.5 w-2 h-2 bg-rose-500 rounded-full ring-2 ring-[#0c0d12]" />
        </button>

        {/* User Profile Avatar */}
        <button
          aria-label="User Profile"
          className="w-8 h-8 rounded-full bg-[#1e212b] border border-white/10 flex items-center justify-center text-gray-400 hover:text-white hover:border-white/25 transition"
        >
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
            <path
              clipRule="evenodd"
              d="M7.5 6a4.5 4.5 0 1 1 9 0 4.5 4.5 0 0 1-9 0ZM3.751 20.105a8.25 8.25 0 0 1 16.498 0 .75.75 0 0 1-.437.695A18.683 18.683 0 0 1 12 22.5c-2.786 0-5.433-.608-7.812-1.7a.75.75 0 0 1-.437-.695Z"
              fillRule="evenodd"
            />
          </svg>
        </button>
      </div>
    </header>
  );
};

export default TopBar;
