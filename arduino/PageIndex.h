const char MAIN_page[] PROGMEM = R"=====(
<!DOCTYPE html>
<html>
<head>
  <title>ESP32 P10 Web Server</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f4; }
    h1 { text-align: center; color: #333; }
    .container { max-width: 600px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
    label { display: block; margin: 10px 0 5px; font-weight: bold; }
    input, select { width: 100%; padding: 8px; margin-bottom: 10px; border: 1px solid #ccc; border-radius: 4px; }
    button { width: 100%; padding: 10px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer; }
    button:hover { background-color: #45a049; }
    .section { margin-bottom: 20px; }
    .hidden { display: none; }
  </style>
</head>
<body>
  <div class="container">
    <h1>ESP32 P10 Web Server</h1>
    <div class="section">
      <label for="key">Key:</label>
      <input type="text" id="key" placeholder="Enter key">
    </div>
    <div class="section">
      <label for="mode">Display Mode:</label>
      <select id="mode" onchange="toggleInputs()">
        <option value="SR">Single Row</option>
        <option value="DBS">Double Row Bold Static</option>
        <option value="DBA">Double Row Bold Animated</option>
        <option value="DBM">Double Row Bold Mixed</option>
      </select>
    </div>
    <div id="singleRow" class="section">
      <label for="singleText">Text:</label>
      <input type="text" id="singleText" placeholder="Enter text for single row">
    </div>
    <div id="doubleRow" class="section hidden">
      <label for="firstText">Text for First Row:</label>
      <input type="text" id="firstText" placeholder="Enter text for first row">
      <label for="firstPos">Text Position for First Row (0-64):</label>
      <input type="number" id="firstPos" min="0" max="64" value="0">
      <label for="secondText">Text for Second Row:</label>
      <input type="text" id="secondText" placeholder="Enter text for second row">
    </div>
    <button onclick="submitSettings()">Submit</button>
  </div>
  <script>
    function toggleInputs() {
      const mode = document.getElementById('mode').value;
      document.getElementById('singleRow').classList.toggle('hidden', mode !== 'SR');
      document.getElementById('doubleRow').classList.toggle('hidden', mode === 'SR');
    }
    function submitSettings() {
      const key = document.getElementById('key').value;
      const mode = document.getElementById('mode').value;
      let settings = key + ',' + mode;
      if (mode === 'SR') {
        settings += ',' + document.getElementById('singleText').value;
      } else {
        settings += ',' + document.getElementById('firstText').value + ',' +
                    document.getElementById('firstPos').value + ',' +
                    document.getElementById('secondText').value;
      }
      fetch('/setText?Settings=' + encodeURIComponent(settings))
        .then(response => response.text())
        .then(data => alert(data === '+OK' ? 'Settings applied!' : 'Error: Invalid key'))
        .catch(error => alert('Error: ' + error));
    }
    toggleInputs();
  </script>
</body>
</html>
)=====";
