// AnimatedWaveCard.jsx
import React from 'react';
import styled from 'styled-components';

const AnimatedWaveCard = ({ title, value, icon, sub, gradientColor }) => {
  return (
    <StyledWrapper $gradient={gradientColor}>
      <div className="e-card playing">
        <div className="image" />
        <div className="wave" />
        <div className="wave" />
        <div className="wave" />
        <div className="infotop">
          <div className="icon-container">{icon}</div>
          <div className="value">{value}</div>
          <div className="title">{title}</div>
          <div className="sub">{sub}</div>
        </div>
      </div>
    </StyledWrapper>
  );
};

const StyledWrapper = styled.div`
  height: 100%;
  
  .e-card {
    background: rgba(15, 23, 42, 0.6); /* Matches dashboard dark theme */
    backdrop-filter: blur(12px);
    box-shadow: 0px 8px 28px -9px rgba(0,0,0,0.45);
    position: relative;
    width: 100%;
    height: 220px; /* Adjusted height for metric cards */
    border-radius: 24px;
    border: 1px solid rgba(51, 65, 85, 0.5);
    overflow: hidden;
  }

  .wave {
    position: absolute;
    width: 540px;
    height: 700px;
    opacity: 0.6;
    left: 0;
    top: 0;
    margin-left: -50%;
    margin-top: -70%;
    /* Use dynamic gradient or fallback to the provided purple/blue */
    background: ${props => props.$gradient || 'linear-gradient(744deg,#af40ff,#5b42f3 60%,#00ddeb)'};
  }

  .icon-container {
    display: flex;
    justify-content: center;
    margin-top: -0.5em;
    padding-bottom: 0.5em;
    color: white;
  }

  .infotop {
    text-align: center;
    position: absolute;
    top: 3em;
    left: 0;
    right: 0;
    color: rgb(255, 255, 255);
    font-weight: 600;
  }

  .value {
    font-size: 36px;
    font-weight: 900;
    margin-bottom: 4px;
  }

  .title {
    font-size: 14px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: #cbd5e1;
  }

  .sub {
    font-size: 11px;
    font-weight: 400;
    color: #94a3b8;
    margin-top: 4px;
    font-family: monospace;
  }

  .wave:nth-child(2),
  .wave:nth-child(3) {
    top: 180px; /* Adjusted wave position for the new height */
  }

  .playing .wave {
    border-radius: 40%;
    animation: wave 3000ms infinite linear;
  }

  .wave {
    border-radius: 40%;
    animation: wave 55s infinite linear;
  }

  .playing .wave:nth-child(2) {
    animation-duration: 4000ms;
  }

  .wave:nth-child(2) {
    animation-duration: 50s;
  }

  .playing .wave:nth-child(3) {
    animation-duration: 5000ms;
  }

  .wave:nth-child(3) {
    animation-duration: 45s;
  }

  @keyframes wave {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
`;

export default AnimatedWaveCard;