const express = require("express");
const cors = require("cors");
const multer = require("multer");
const Tesseract = require("tesseract.js");
const fs = require("fs");

const app = express();
app.use(cors());
app.use(express.json());

const upload = multer({ dest: "uploads/" });

function cleanMenuItems(rawText) {
  return rawText
    .split("\n")
    .map(line =>
      line
        .replace(/[^A-Za-z ]/g, "")
        .replace(/\s+/g, " ")
        .trim()
    )
    .filter(line => line.length > 2)
    .filter(line => {
      const blacklist = [
        "lunch",
        "dinner",
        "menu",
        "timing",
        "date",
        "pm",
        "am",
        "to"
      ];
      return !blacklist.some(word =>
        line.toLowerCase().includes(word)
      );
    })
    .map(line =>
      line
        .toLowerCase()
        .split(" ")
        .map(w => w.charAt(0).toUpperCase() + w.slice(1))
        .join(" ")
    );
}

app.post("/ocr", upload.single("image"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: "No image uploaded" });
    }

    const imagePath = req.file.path;

    const result = await Tesseract.recognize(imagePath, "eng");
    const rawText = result.data.text;

    const menuItems = cleanMenuItems(rawText);

    const data = {
      date: new Date().toISOString().split("T")[0],
      menuItems,
    };

    fs.writeFileSync("./data/menu.json", JSON.stringify(data, null, 2));
    fs.unlinkSync(imagePath);

    res.json({ menuItems });
  } catch (err) {
    console.error("OCR ERROR:", err);
    res.status(500).json({ error: "OCR failed" });
  }
});

app.listen(5000, () => {
  console.log("Backend running on http://localhost:5000");
});
