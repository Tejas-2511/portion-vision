export default function Analysis() {
  return (
    <div style={{ fontFamily: "Arial", backgroundColor: "#f5f5f5", minHeight: "100vh" }}>
      
      {/* AppBar */}
      <div
        style={{
          backgroundColor: "green",
          color: "white",
          padding: "15px 20px",
          fontSize: "20px",
          fontWeight: "bold",
        }}
      >
        Portion Analysis
      </div>

      {/* Body */}
      <div style={{ padding: "16px" }}>

        {/* Recommended Portion */}
        <div style={cardStyle}>
          <div style={cardInnerStyle}>
            Recommended Portion Placeholder
          </div>
        </div>

        {/* Captured Image */}
        <div style={cardStyle}>
          <div style={cardInnerStyle}>
            Captured Plate Image Placeholder
          </div>
        </div>

        {/* Comparison */}
        <div style={cardStyle}>
          <div style={cardInnerStyle}>
            Portion Comparison Result Placeholder
          </div>
        </div>

      </div>
    </div>
  );
}

const cardStyle = {
  backgroundColor: "white",
  borderRadius: "12px",
  padding: "12px",
  boxShadow: "0px 2px 6px rgba(0,0,0,0.2)",
  marginBottom: "20px",
};

const cardInnerStyle = {
  height: "120px",
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  backgroundColor: "#e0e0e0",
  borderRadius: "10px",
  fontSize: "16px",
};
