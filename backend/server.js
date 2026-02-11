const express = require("express");
const cors = require("cors");
const multer = require("multer");
const Tesseract = require("tesseract.js");
const fs = require("fs");
const sharp = require("sharp");

const app = express();
app.use(cors());
app.use(express.json());

const upload = multer({ dest: "uploads/" });

function cleanMenuItems(rawText) {
  const blacklist = ["menu", "breakfast", "lunch", "dinner"];

  return rawText
    .split("\n")
    .map(line => line.trim())
    .filter(line => line.length > 1)
    .map(line => {
      line = line.replace(/[^A-Za-z, &/]/g, "");
      line = line.replace(/\s+/g, " ").trim();

      let parts = [line];

      parts = parts
        .flatMap(x => x.split(","))
        .flatMap(x => x.split("/"))
        .flatMap(x => x.split("&"))
        .map(x => x.trim())
        .filter(x => x.length > 1);

      return parts;
    })
    .flat()
    .map(line =>
      line
        .toLowerCase()
        .split(" ")
        .map(w => w.charAt(0).toUpperCase() + w.slice(1))
        .join(" ")
    )
    .filter(line => line.length > 1)
    .filter(line => !blacklist.some(word => line.toLowerCase().includes(word)))
    .filter((item, index, self) => self.indexOf(item) === index);
}

app.post("/ocr", upload.single("image"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: "No image uploaded" });
    }

    const originalPath = req.file.path;
    const processedPath = `uploads/processed-${Date.now()}.png`;

    await sharp(originalPath)
      .extend({
        top: 40,
        bottom: 20,
        left: 20,
        right: 20,
        background: { r: 255, g: 255, b: 255 }
      })
      .resize({ width: 1200 })
      .grayscale()
      .normalize()
      .threshold(160)
      .sharpen()
      .toFile(processedPath);

    const result = await Tesseract.recognize(processedPath, "eng", {
      tessedit_pageseg_mode: 6,
    });

    const rawText = result.data.text;

    const menuItems = cleanMenuItems(rawText);

    const data = {
      date: new Date().toISOString().split("T")[0],
      menuItems,
    };

    fs.writeFileSync("./data/menu.json", JSON.stringify(data, null, 2));

    fs.unlinkSync(originalPath);
    fs.unlinkSync(processedPath);

    res.json({ menuItems });
  } catch (err) {
    console.error("OCR ERROR:", err);
    res.status(500).json({ error: "OCR failed" });
  }
});

app.listen(5000, () => {
  console.log("Backend running on http://localhost:5000");
});
