const express = require("express");
const cors = require("cors");
const multer = require("multer");
const Tesseract = require("tesseract.js");
const fs = require("fs");

const app = express();
app.use(cors());
app.use(express.json());

const upload = multer({ dest: "uploads/" });

app.post("/ocr", upload.single("image"), async (req, res) => {
  try {
    const imagePath = req.file.path;

    const result = await Tesseract.recognize(imagePath, "eng");
    const text = result.data.text;

    // Save extracted text into JSON file
    const data = {
      date: new Date().toISOString().split("T")[0],
      extractedText: text
    };

    fs.writeFileSync("./data/menu.json", JSON.stringify(data, null, 2));

    res.json({ text });
  } catch (err) {
    console.log(err);
    res.status(500).json({ error: "OCR failed" });
  }
});

app.listen(5000, () => {
  console.log("Backend running on http://localhost:5000");
});
