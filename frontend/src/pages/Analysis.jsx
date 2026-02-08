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

export default function Analysis() {
  return (
    <div style={{ fontFamily: "Arial", backgroundColor: "#f5f5f5", minHeight: "100vh" }}>
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

      <div style={{ padding: "16px" }}>
        <div style={cardStyle}>
          <div style={cardInnerStyle}>
            Recommended Portion Placeholder
          </div>
        </div>

        <div style={cardStyle}>
          <div style={cardInnerStyle}>
            Captured Plate Image Placeholder
          </div>
        </div>

        <div style={cardStyle}>
          <div style={cardInnerStyle}>
            Portion Comparison Result Placeholder
          </div>
        </div>
      </div>
    </div>
  );
}
