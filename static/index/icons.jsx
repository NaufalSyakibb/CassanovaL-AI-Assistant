/* ============================================================
   Icons — thin-line SVG set, replaces emoji
   ============================================================ */
const S = ({ size = 16, children, stroke = 1.5 }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} fill="none"
    stroke="currentColor" strokeWidth={stroke}
    strokeLinecap="round" strokeLinejoin="round">{children}</svg>
);

const IcoSend       = ({size=16})=> <S size={size}><path d="M5 12h14M13 6l6 6-6 6"/></S>;
const IcoSearch     = ({size=16})=> <S size={size}><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></S>;
const IcoClock      = ({size=12})=> <S size={size}><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></S>;
const IcoFile       = ({size=14})=> <S size={size}><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/></S>;
const IcoCmd        = ({size=16})=> <S size={size}><path d="M18 3a3 3 0 1 0 0 6h-3v-3a3 3 0 0 0-3-3 3 3 0 0 0-3 3 3 3 0 0 0 3 3h12"/><path d="M6 21a3 3 0 1 0 0-6h3v3a3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0-3-3H3"/></S>;
const IcoUsers      = ({size=16})=> <S size={size}><circle cx="9" cy="9" r="3.5"/><path d="M2.5 20c0-3 3-5 6.5-5s6.5 2 6.5 5"/><circle cx="17" cy="8" r="3"/><path d="M22 18c0-2.2-2-4-4.5-4"/></S>;
const IcoX          = ({size=14})=> <S size={size} stroke={2}><path d="M6 6l12 12M18 6l-12 12"/></S>;
const IcoClip       = ({size=16})=> <S size={size}><path d="M21 11.5l-8.5 8.5a5.5 5.5 0 0 1-7.8-7.8l8.5-8.5a3.5 3.5 0 0 1 5 5l-8.5 8.5a1.5 1.5 0 0 1-2.1-2.1l7.8-7.8"/></S>;
const IcoRocket     = ({size=16})=> <S size={size}><path d="M4.5 16.5c-1 1-1.5 4-1.5 4s3-.5 4-1.5a1.8 1.8 0 1 0-2.5-2.5z"/><path d="M12 15l-3-3a20 20 0 0 1 4-7c3.5-3.5 8-3 8-3s.5 4.5-3 8a20 20 0 0 1-7 4z"/><circle cx="15" cy="9" r="1.5"/></S>;
const IcoPanelClose = ({size=15})=> <S size={size}><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16"/><path d="m10 9 3 3-3 3"/></S>;
const IcoPanelOpen  = ({size=15})=> <S size={size}><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16"/><path d="m20 9-3 3 3 3"/></S>;
const IcoSun        = ({size=15})=> <S size={size}><circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.5 5.5l1.5 1.5M17 17l1.5 1.5M5.5 18.5l1.5-1.5M17 7l1.5-1.5"/></S>;
const IcoMoon       = ({size=15})=> <S size={size}><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/></S>;
const IcoDownload   = ({size=13})=> <S size={size}><path d="M12 4v12"/><path d="m7 11 5 5 5-5"/><path d="M5 20h14"/></S>;
const IcoArrowRight = ({size=13})=> <S size={size}><path d="M5 12h14M13 6l6 6-6 6"/></S>;
const IcoPlus       = ({size=14})=> <S size={size}><path d="M12 5v14M5 12h14"/></S>;
const IcoUpload     = ({size=20})=> <S size={size}><path d="M12 20V8"/><path d="m7 13 5-5 5 5"/><path d="M5 4h14"/></S>;
const IcoCheck      = ({size=14})=> <S size={size}><path d="m5 12 4.5 4.5L19 7"/></S>;
const IcoReceipt    = ({size=20})=> <S size={size}><path d="M5 3v18l2-1.5L9 21l2-1.5L13 21l2-1.5L17 21l2-1.5V3H5z"/><path d="M8 8h8M8 12h8M8 16h5"/></S>;
const IcoSparkle    = ({size=14})=> <S size={size}><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/></S>;
const IcoDashboard  = ({size=14})=> <S size={size}><rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/></S>;
const IcoChat       = ({size=14})=> <S size={size}><path d="M4 5h16v11H8l-4 4V5z"/></S>;
const IcoLeaf       = ({size=14})=> <S size={size}><path d="M20 4S11 4 7 8s-4 11-4 11 7 0 11-4 6-11 6-11z"/><path d="M3 19 12 10"/></S>;
const IcoFeather    = ({size=14})=> <S size={size}><path d="M20 4s-5 0-10 5-5 10-5 10l2 2s5 0 10-5 5-10 5-10z"/><path d="M5 19l7-7"/></S>;
const IcoNewspaper  = ({size=14})=> <S size={size}><rect x="3" y="4" width="14" height="16" rx="1"/><path d="M17 8h4v10a2 2 0 0 1-2 2H7"/><path d="M7 8h6M7 12h6M7 16h6"/></S>;
const IcoCode       = ({size=14})=> <S size={size}><path d="m8 8-5 4 5 4M16 8l5 4-5 4M14 5l-4 14"/></S>;
const IcoCalendar   = ({size=14})=> <S size={size}><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></S>;
const IcoCoin       = ({size=14})=> <S size={size}><circle cx="12" cy="12" r="9"/><path d="M12 6v12M9 9h5a2 2 0 0 1 0 4H9h6a2 2 0 0 1 0 4H9"/></S>;
const IcoHeart      = ({size=14})=> <S size={size}><path d="M12 20s-7-4.5-7-10a4 4 0 0 1 7-2.5A4 4 0 0 1 19 10c0 5.5-7 10-7 10z"/></S>;
const IcoBook       = ({size=14})=> <S size={size}><path d="M4 4h6a3 3 0 0 1 3 3v13a2 2 0 0 0-2-2H4z"/><path d="M20 4h-6a3 3 0 0 0-3 3v13a2 2 0 0 1 2-2h7z"/></S>;
const IcoLamp       = ({size=14})=> <S size={size}><path d="M9 18h6M10 22h4M8 14a6 6 0 1 1 8 0l-1 3H9z"/></S>;
const IcoCandlestick= ({size=16})=> <S size={size}><path d="M9 4v3M9 13v3M15 8v3M15 17v3"/><rect x="7" y="7" width="4" height="6" rx="0.5"/><rect x="13" y="11" width="4" height="6" rx="0.5"/></S>;
const IcoChart      = ({size=14})=> <S size={size}><path d="M3 20h18M3 20V8l5 4 4-6 4 4 5-6"/></S>;
const IcoTrend      = ({size=14})=> <S size={size}><path d="M22 7l-8 8-4-4-7 7"/><path d="M16 7h6v6"/></S>;
const IcoBell       = ({size=15})=> <S size={size}><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a2 2 0 0 0 3.4 0"/></S>;
const IcoMic        = ({size=16})=> <S size={size}><path d="M12 2a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/><path d="M19 10a7 7 0 0 1-14 0M12 19v3M8 22h8"/></S>;
const IcoMicOff     = ({size=16})=> <S size={size}><line x1="2" y1="2" x2="22" y2="22"/><path d="M18.9 10A7 7 0 0 1 5 15.7M12 19v3M8 22h8"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V5a3 3 0 0 0-5.94-.6"/></S>;
const IcoPixel = ({size=15}) => (
  <svg viewBox="0 0 15 15" width={size} height={size} fill="currentColor">
    <rect x="0" y="0" width="4" height="4"/>
    <rect x="6" y="0" width="4" height="4"/>
    <rect x="0" y="6" width="4" height="4"/>
    <rect x="6" y="6" width="4" height="4"/>
    <rect x="0" y="11" width="4" height="4"/>
    <rect x="6" y="11" width="4" height="4"/>
  </svg>
);
const IcoRefresh    = ({size=14})=> <S size={size}><path d="M1 4v6h6"/><path d="M23 20v-6h-6"/><path d="M20.5 9A9 9 0 0 0 5.2 5.2L1 10M23 14l-4.2 4.8A9 9 0 0 1 3.5 15"/></S>;

window.Icons = {
  IcoSend, IcoSearch, IcoClock, IcoFile, IcoCmd, IcoUsers, IcoX, IcoClip,
  IcoRocket, IcoPanelClose, IcoPanelOpen, IcoSun, IcoMoon, IcoPixel, IcoDownload,
  IcoArrowRight, IcoPlus, IcoUpload, IcoCheck, IcoReceipt, IcoSparkle,
  IcoDashboard, IcoChat, IcoLeaf, IcoFeather, IcoNewspaper, IcoCode,
  IcoCalendar, IcoCoin, IcoHeart, IcoBook, IcoLamp, IcoCandlestick,
  IcoChart, IcoTrend, IcoBell, IcoMic, IcoMicOff, IcoRefresh,
};
