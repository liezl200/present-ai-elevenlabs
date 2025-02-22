import React from "react";

export const PresentableLogo = ({
  className,
  width,
  height,
}: {
  className?: string;
  width?: number;
  height?: number;
}) => (
  <svg
    width={width || 200}
    height={height || 50}
    className={className}
    viewBox="0 0 800 100"
    fill="currentColor"
    xmlns="http://www.w3.org/2000/svg"
  >
    {/* "P" Letter */}
    <path
      d="M40 10H70C90 10 105 25 105 50C105 75 90 90 70 90H40V10Z"
      fill="currentColor"
    />
    <circle cx="75" cy="50" r="15" fill="black" />

    {/* "RESENTABLE" Text */}
    <text
      x="130"
      y="75"
      fontFamily="Arial, sans-serif"
      fontSize="80"
      fontWeight="bold"
      fill="currentColor"
    >
      present.ai
    </text>
  </svg>
);
