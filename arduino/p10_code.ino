//>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> 03_ESP32_P10_Set_Text_Via_Web_Server_-_SM (Station Mode) with Audio Feedback
//----------------------------------------Load libraries
#include <WiFi.h>
#include <WebServer.h>
#include <DMD32.h>
#include "fonts/SystemFont5x7.h"
#include "fonts/Arial_black_16.h"
#include "PageIndex.h" //--> Include the contents of the User Interface Web page, stored in the same folder as the .ino file
#include <Preferences.h>
#include <driver/i2s.h>
#include <math.h>
//----------------------------------------

//----------------------------------------Audio Configuration
#define I2S_BCLK  26  // Bit Clock
#define I2S_LRC   25  // Word Select (LRCLK)
#define I2S_DOUT  4   // Data Out (DIN)

const int sampleRate = 44100;
const float alertDuration = 60.0;      // Duration of each alert cycle (seconds) - 60 seconds as requested

// Parking violation alert parameters
const float beepDuration = 0.5;       // Duration of each beep (seconds)  
const float silenceDuration = 0.5;    // Delay between beeps (seconds)
const float volume = 1.0;             // Volume level (0.0 to 1.0) - MAX VOLUME
const int constantFreq = 1800;        // Single high frequency tone (Hz)

// Audio control variables
bool audioAlertActive = false;
unsigned long audioStartTime = 0;
bool audioSystemInitialized = false;
//----------------------------------------

//----------------------------------------Defining the key.
// "Key" functions like a password. In order to change the text on the P10, the user must know the "key".
// You can change it to another word.
#define key_Txt "uom"
//----------------------------------------

// Fire up the DMD library as dmd.
#define DISPLAYS_ACROSS 2
#define DISPLAYS_DOWN 1
DMD dmd(DISPLAYS_ACROSS, DISPLAYS_DOWN);

// Timer setup.
// create a hardware timer  of ESP32
hw_timer_t * timer = NULL;

//----------------------------------------SSID and PASSWORD of your WiFi network.
const char* ssid = "YOUR_WIFI_SSID";          // <-- set your WiFi network name
const char* password = "YOUR_WIFI_PASSWORD";  // <-- set your WiFi password
//----------------------------------------

String display_Modes = "";
String single_Row_Txt = "";
String single_Row_Txt_Orig = ""; // Store original input with spaces
String double_Row_First_Txt = "";
String double_Row_First_Txt_Orig = ""; // Store original input with spaces
int double_Row_First_Txt_Pos = 0;
String double_Row_Second_Txt = "";
String double_Row_Second_Txt_Orig = ""; // Store original input with spaces

// Server on port 80.
WebServer server(80);  

// Initialize Preferences.
Preferences preferences;

//________________________________________________________________________________initializeAudioSystem()
// Initialize I2S audio system
void initializeAudioSystem() {
  if (audioSystemInitialized) return;
  
  Serial.println("Initializing audio system...");
  
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = sampleRate,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
    .communication_format = I2S_COMM_FORMAT_I2S_MSB,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 64,
    .use_apll = false,
    .tx_desc_auto_clear = true,
    .fixed_mclk = 0
  };
  
  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_BCLK,
    .ws_io_num = I2S_LRC,
    .data_out_num = I2S_DOUT,
    .data_in_num = -1
  };
  
  esp_err_t result = i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  if (result == ESP_OK) {
    i2s_set_pin(I2S_NUM_0, &pin_config);
    audioSystemInitialized = true;
    Serial.println("Audio system initialized successfully");
  } else {
    Serial.printf("Failed to initialize audio system: %d\n", result);
  }
}
//________________________________________________________________________________

//________________________________________________________________________________generateAlertTone()
// Generate alert tone for unauthorized vehicle - High Volume Beep with 0.5s Delay
void generateAlertTone() {
  if (!audioSystemInitialized) return;
  
  static double phase = 0.0;
  static unsigned long startTime = millis();
  
  int16_t samples[512]; // Larger buffer for better sound quality
  size_t bytes_written;
  
  unsigned long currentTime = millis();
  
  // Calculate cycle position (beep + silence = 1 second total cycle)
  float totalCycle = beepDuration + silenceDuration; // 1 second total
  float cycleTime = fmod((currentTime - startTime) / 1000.0, totalCycle);
  
  bool generateSound = (cycleTime < beepDuration); // Sound for first 0.5s, silence for next 0.5s
  
  // Generate samples - beep with 0.5s delay pattern
  for (int i = 0; i < 512; i += 2) {
    int16_t sample = 0;
    
    if (generateSound) {
      // Generate high-pitched beep at maximum volume
      double sampleValue = sin(phase) * 32767.0 * volume;
      sample = (int16_t)sampleValue;
      
      phase += 2 * M_PI * constantFreq / sampleRate;
      if (phase >= 2 * M_PI) phase -= 2 * M_PI;
    } else {
      // Silence period
      sample = 0;
      phase = 0.0; // Reset phase during silence for clean restart
    }
    
    samples[i] = sample;     // Left channel
    samples[i + 1] = sample; // Right channel
  }

  i2s_write(I2S_NUM_0, samples, sizeof(samples), &bytes_written, portMAX_DELAY);
}
//________________________________________________________________________________

//________________________________________________________________________________startUnauthorizedAlert()
// Start audio alert for unauthorized vehicle
void startUnauthorizedAlert() {
  if (!audioSystemInitialized) {
    initializeAudioSystem();
  }
  
  if (audioSystemInitialized && !audioAlertActive) {
    audioAlertActive = true;
    audioStartTime = millis();
    Serial.println("🔊 Starting unauthorized vehicle audio alert");
  }
}
//________________________________________________________________________________

//________________________________________________________________________________stopUnauthorizedAlert()
// Stop audio alert
void stopUnauthorizedAlert() {
  if (audioAlertActive) {
    audioAlertActive = false;
    Serial.println("🔇 Stopping unauthorized vehicle audio alert");
    
    // Clear any remaining audio buffer
    if (audioSystemInitialized) {
      int16_t silence[512];
      memset(silence, 0, sizeof(silence));
      size_t bytes_written;
      i2s_write(I2S_NUM_0, silence, sizeof(silence), &bytes_written, 0);
    }
  }
}
//________________________________________________________________________________

//________________________________________________________________________________processAudioAlert()
// Process audio alert (call this in main loop)
void processAudioAlert() {
  if (!audioAlertActive) return;
  
  // Check if alert duration has elapsed
  if (millis() - audioStartTime > (alertDuration * 1000)) {
    stopUnauthorizedAlert();
    return;
  }
  
  // Generate alert tone
  generateAlertTone();
}
//________________________________________________________________________________

//________________________________________________________________________________reduceWordSpacing()
// Helper function to remove all spaces for non-animated storage
String reduceWordSpacing(String input) {
  String result = "";
  for (int i = 0; i < input.length(); i++) {
    char c = input.charAt(i);
    if (c != ' ') {
      result += c;
    }
  }
  return result;
}
//________________________________________________________________________________

//________________________________________________________________________________IRAM_ATTR triggerScan()
// Interrupt handler for Timer1 (TimerOne) driven DMD refresh scanning, 
// this gets called at the period set in Timer1.initialize();
void IRAM_ATTR triggerScan() {
  dmd.scanDisplayBySPI();
}
//________________________________________________________________________________

//________________________________________________________________________________handleRoot()
// This routine is executed when you open ESP32 IP Address in browser.
void handleRoot() {
  server.send(200, "text/html", MAIN_page); //Send web page
}
//________________________________________________________________________________

//________________________________________________________________________________handleSettings()
// Subroutine to handle settings. The displayed text and others are set here.
void handleSettings() {
  timerAlarmDisable(timer);
  delay(1000);
  
  String incoming_Settings = server.arg("Settings");
  Serial.println();
  Serial.print("Incoming settings : ");
  Serial.println(incoming_Settings);
  
  if (getValue(incoming_Settings, ',', 0) == key_Txt) {
    display_Modes = getValue(incoming_Settings, ',', 1);

    if (display_Modes == "SR") {
      single_Row_Txt_Orig = getValue(incoming_Settings, ',', 2);
      single_Row_Txt = reduceWordSpacing(single_Row_Txt_Orig);
      
      // Save texts and modes to flash memory.
      preferences.begin("P10_SD", false);
      preferences.putString("DM", display_Modes);
      preferences.putString("SRT", single_Row_Txt);
      preferences.putString("SRTO", single_Row_Txt_Orig);
      preferences.end();
      delay(500);
    }
  
    if (display_Modes == "DBS" || display_Modes == "DBA" || display_Modes == "DBM") {
      double_Row_First_Txt_Orig = getValue(incoming_Settings, ',', 2);
      double_Row_First_Txt = reduceWordSpacing(double_Row_First_Txt_Orig);
      double_Row_First_Txt_Pos = getValue(incoming_Settings, ',', 3).toInt();
      double_Row_Second_Txt_Orig = getValue(incoming_Settings, ',', 4);
      double_Row_Second_Txt = reduceWordSpacing(double_Row_Second_Txt_Orig);
      
      // Save texts and modes to flash memory.
      preferences.begin("P10_SD", false);
      preferences.putString("DM", display_Modes);
      preferences.putString("DRFT", double_Row_First_Txt);
      preferences.putString("DRFTO", double_Row_First_Txt_Orig);
      preferences.putInt("DRFTP", double_Row_First_Txt_Pos);
      preferences.putString("DRST", double_Row_Second_Txt);
      preferences.putString("DRSTO", double_Row_Second_Txt_Orig);
      preferences.end();
      delay(500);
    }

    // Handle audio alert command
    if (display_Modes == "AUDIO_ALERT") {
      String command = getValue(incoming_Settings, ',', 2);
      if (command == "START") {
        startUnauthorizedAlert();
        Serial.println("Audio alert started via web command");
      } else if (command == "STOP") {
        stopUnauthorizedAlert();
        Serial.println("Audio alert stopped via web command");
      }
    }

    server.send(200, "text/plain", "+OK"); //--> Sending replies to the client.
    delay(500);
  } else {
    server.send(200, "text/plain", "+ERR"); //--> Sending replies to the client.
    delay(500);
  }
  
  timerAlarmEnable(timer);
  delay(500);
}
//________________________________________________________________________________

//________________________________________________________________________________getValue()
// String function to split strings based on certain characters.
String getValue(String data, char separator, int index) {
  int found = 0;
  int strIndex[] = { 0, -1 };
  int maxIndex = data.length() - 1;
  
  for (int i = 0; i <= maxIndex && found <= index; i++) {
    if (data.charAt(i) == separator || i == maxIndex) {
      found++;
      strIndex[0] = strIndex[1] + 1;
      strIndex[1] = (i == maxIndex) ? i+1 : i;
    }
  }
  return found > index ? data.substring(strIndex[0], strIndex[1]) : "";
}
//________________________________________________________________________________ 

//________________________________________________________________________________Single_Row_Display_Mode()
// Subroutine for displaying "running text" on P10 in Single Row mode with proper word spacing.
void Single_Row_Display_Mode() {
  String processed_text = single_Row_Txt_Orig;
  processed_text.trim();
  
  dmd.clearScreen(true);
  dmd.selectFont(Arial_Black_16);

  // Split text into words and calculate total length with proper spacing
  String word = "";
  int total_length = 0;
  int word_count = 0;
  for (int i = 0; i <= processed_text.length(); i++) {
    if (i == processed_text.length() || processed_text.charAt(i) == ' ') {
      if (word.length() > 0) {
        total_length += word.length() * 10; // Approx 10 pixels per char in Arial_Black_16
        if (word_count > 0) total_length += 8; // 8-pixel gap between words for better spacing
        word_count++;
        word = "";
      }
    } else {
      word += processed_text.charAt(i);
    }
  }

  int x_pos = (32 * DISPLAYS_ACROSS) + 1; // Start 1 pixel from right edge
  long start = millis();
  long timer = start;
  int scrl_long = total_length + (32 * DISPLAYS_ACROSS);

  while (true) {
    if ((timer + 30) < millis()) {
      dmd.clearScreen(true);
      int current_x = x_pos;
      String current_word = "";
      int word_index = 0;
      for (int i = 0; i <= processed_text.length(); i++) {
        if (i == processed_text.length() || processed_text.charAt(i) == ' ') {
          if (current_word.length() > 0) {
            char word_array[current_word.length() + 1];
            current_word.toCharArray(word_array, current_word.length() + 1);
            dmd.drawString(current_x, 0, word_array, current_word.length(), GRAPHICS_NORMAL);
            current_x += (current_word.length() * 10);
            if (word_index < word_count - 1) {
              current_x += 8; // 8-pixel gap between words for better spacing
            }
            current_word = "";
            word_index++;
          }
        } else {
          current_word += processed_text.charAt(i);
        }
      }
      if (x_pos > -scrl_long) {
        x_pos--;
      } else {
        break;
      }
      timer = millis();
    }
    
    // Process audio alert during display updates
    processAudioAlert();
  }
  delay(1000);
}
//________________________________________________________________________________ 

//________________________________________________________________________________Double_Row_Display_Mode()
// Subroutine to display text in the first row and display "running text" in the second row in Double Row mode.
void Double_Row_Display_Mode() {
  // Use original string for first row to split words
  String processed_first_text_orig = double_Row_First_Txt_Orig;
  processed_first_text_orig.trim();
  String processed_second_text = double_Row_Second_Txt; // Space-free for animation
  
  dmd.clearScreen(true);
  dmd.selectFont(SystemFont5x7);

  // Split first text into words and render with 4-pixel gap, starting at double_Row_First_Txt_Pos + 1
  int x_pos = double_Row_First_Txt_Pos + 1;
  String word = "";
  for (int i = 0; i <= processed_first_text_orig.length(); i++) {
    if (i == processed_first_text_orig.length() || processed_first_text_orig.charAt(i) == ' ') {
      if (word.length() > 0) {
        char word_array[word.length() + 1];
        word.toCharArray(word_array, word.length() + 1);
        dmd.drawString(x_pos, 0, word_array, word.length(), GRAPHICS_NORMAL);
        x_pos += (word.length() * 6) + 4; // 5 pixels per char + 1 pixel gap + 4 pixels between words
        word = "";
      }
    } else {
      word += processed_first_text_orig.charAt(i);
    }
  }

  // Animate second row (space-free), starting 1 pixel from right edge
  char CA_double_Row_Second_Txt[processed_second_text.length() + 1];
  processed_second_text.toCharArray(CA_double_Row_Second_Txt, processed_second_text.length() + 1);
  
  int scrl_long = (processed_second_text.length()*6) + (32*DISPLAYS_ACROSS);
  int i = (32*DISPLAYS_ACROSS) + 1;
  long start=millis();
  long timer=start;
  while(true){
    if ((timer+30) < millis()) {
      dmd.drawString(i, 9, CA_double_Row_Second_Txt, processed_second_text.length(), GRAPHICS_NORMAL);
      if (i > ~scrl_long) {
        i--;
      } else {
        break;
      }
      timer=millis();
    }
    
    // Process audio alert during display updates
    processAudioAlert();
  }
}
//________________________________________________________________________________ 

//________________________________________________________________________________Double_Row_Bold_Static_Display_Mode()
// Function 1: Two rows with small font text (both static, 4-pixel gap between words)
void Double_Row_Bold_Static_Display_Mode() {
  // Use original strings to split words
  String processed_first_text_orig = double_Row_First_Txt_Orig;
  processed_first_text_orig.trim();
  String processed_second_text_orig = double_Row_Second_Txt_Orig;
  processed_second_text_orig.trim();
  
  dmd.clearScreen(true);
  dmd.selectFont(SystemFont5x7);

  // Split first text into words and render with 4-pixel gap, starting at double_Row_First_Txt_Pos + 1
  int x_pos = double_Row_First_Txt_Pos + 1;
  String word = "";
  for (int i = 0; i <= processed_first_text_orig.length(); i++) {
    if (i == processed_first_text_orig.length() || processed_first_text_orig.charAt(i) == ' ') {
      if (word.length() > 0) {
        char word_array[word.length() + 1];
        word.toCharArray(word_array, word.length() + 1);
        dmd.drawString(x_pos, 0, word_array, word.length(), GRAPHICS_NORMAL);
        x_pos += (word.length() * 6) + 4; // 5 pixels per char + 1 pixel gap + 4 pixels between words
        word = "";
      }
    } else {
      word += processed_first_text_orig.charAt(i);
    }
  }

  // Split second text into words and render with 4-pixel gap, starting at X=1
  x_pos = 1;
  word = "";
  for (int i = 0; i <= processed_second_text_orig.length(); i++) {
    if (i == processed_second_text_orig.length() || processed_second_text_orig.charAt(i) == ' ') {
      if (word.length() > 0) {
        char word_array[word.length() + 1];
        word.toCharArray(word_array, word.length() + 1);
        dmd.drawString(x_pos, 9, word_array, word.length(), GRAPHICS_NORMAL);
        x_pos += (word.length() * 6) + 4; // 5 pixels per char + 1 pixel gap + 4 pixels between words
        word = "";
      }
    } else {
      word += processed_second_text_orig.charAt(i);
    }
  }

  // Hold display for 2 seconds while processing audio
  unsigned long holdStart = millis();
  while (millis() - holdStart < 2000) {
    processAudioAlert();
    delay(10); // Small delay to prevent watchdog issues
  }
}
//________________________________________________________________________________ 

//________________________________________________________________________________Double_Row_Bold_Both_Animated_Display_Mode()
// Function 2: Two rows with small font text and animation (both rows animated, 5-pixel word spacing)
void Double_Row_Bold_Both_Animated_Display_Mode() {
  String processed_first_text = double_Row_First_Txt_Orig;
  processed_first_text.trim();
  String processed_second_text = double_Row_Second_Txt_Orig;
  processed_second_text.trim();
  
  dmd.clearScreen(true);
  dmd.selectFont(SystemFont5x7);

  // Calculate scroll lengths with 5-pixel gaps
  int first_total_length = 0;
  int second_total_length = 0;
  int word_count = 0;
  String word = "";
  
  for (int i = 0; i <= processed_first_text.length(); i++) {
    if (i == processed_first_text.length() || processed_first_text.charAt(i) == ' ') {
      if (word.length() > 0) {
        first_total_length += word.length() * 6; // 5 pixels per char + 1 pixel gap
        if (word_count > 0) first_total_length += 5; // 5-pixel gap between words
        word_count++;
        word = "";
      }
    } else {
      word += processed_first_text.charAt(i);
    }
  }
  
  word = "";
  word_count = 0;
  for (int i = 0; i <= processed_second_text.length(); i++) {
    if (i == processed_second_text.length() || processed_second_text.charAt(i) == ' ') {
      if (word.length() > 0) {
        second_total_length += word.length() * 6;
        if (word_count > 0) second_total_length += 5;
        word_count++;
        word = "";
      }
    } else {
      word += processed_second_text.charAt(i);
    }
  }

  int first_scrl_long = first_total_length + (32 * DISPLAYS_ACROSS);
  int second_scrl_long = second_total_length + (32 * DISPLAYS_ACROSS);
  int first_i = (32 * DISPLAYS_ACROSS) + 1;
  int second_i = (32 * DISPLAYS_ACROSS) + 1;
  long start = millis();
  long timer = start;
  boolean first_done = false;
  boolean second_done = false;

  while (!first_done || !second_done) {
    if ((timer + 30) < millis()) {
      dmd.clearScreen(true);

      // Animate first row
      if (!first_done) {
        int current_x = first_i;
        String current_word = "";
        for (int j = 0; j <= processed_first_text.length(); j++) {
          if (j == processed_first_text.length() || processed_first_text.charAt(j) == ' ') {
            if (current_word.length() > 0) {
              char word_array[current_word.length() + 1];
              current_word.toCharArray(word_array, current_word.length() + 1);
              dmd.drawString(current_x, 0, word_array, current_word.length(), GRAPHICS_NORMAL);
              current_x += (current_word.length() * 6) + 5; // 5 pixels per char + 1 pixel gap + 5 pixels
              current_word = "";
            }
          } else {
            current_word += processed_first_text.charAt(j);
          }
        }
        if (first_i > -first_scrl_long) {
          first_i--;
        } else {
          first_done = true;
        }
      }

      // Animate second row
      if (!second_done) {
        int current_x = second_i;
        String current_word = "";
        for (int j = 0; j <= processed_second_text.length(); j++) {
          if (j == processed_second_text.length() || processed_second_text.charAt(j) == ' ') {
            if (current_word.length() > 0) {
              char word_array[current_word.length() + 1];
              current_word.toCharArray(word_array, current_word.length() + 1);
              dmd.drawString(current_x, 9, word_array, current_word.length(), GRAPHICS_NORMAL);
              current_x += (current_word.length() * 6) + 5;
              current_word = "";
            }
          } else {
            current_word += processed_second_text.charAt(j);
          }
        }
        if (second_i > -second_scrl_long) {
          second_i--;
        } else {
          second_done = true;
        }
      }

      timer = millis();
    }
    
    // Process audio alert during display updates
    processAudioAlert();
  }
  delay(1000);
}
//________________________________________________________________________________ 

//________________________________________________________________________________Double_Row_Bold_Mixed_Display_Mode()
// Function 3: Two rows with small font text - first row static, second row animated with 5-pixel word spacing
void Double_Row_Bold_Mixed_Display_Mode() {
  String processed_first_text_orig = double_Row_First_Txt_Orig;
  processed_first_text_orig.trim();
  String processed_second_text = double_Row_Second_Txt_Orig;
  processed_second_text.trim();
  
  dmd.clearScreen(true);
  dmd.selectFont(SystemFont5x7);

  // Calculate scroll length for second row with 5-pixel gaps
  int second_total_length = 0;
  int word_count = 0;
  String word = "";
  for (int i = 0; i <= processed_second_text.length(); i++) {
    if (i == processed_second_text.length() || processed_second_text.charAt(i) == ' ') {
      if (word.length() > 0) {
        second_total_length += word.length() * 6;
        if (word_count > 0) second_total_length += 5;
        word_count++;
        word = "";
      }
    } else {
      word += processed_second_text.charAt(i);
    }
  }

  int scrl_long = second_total_length + (32 * DISPLAYS_ACROSS);
  int i = (32 * DISPLAYS_ACROSS) + 1;
  long start = millis();
  long timer = start;

  while (true) {
    if ((timer + 30) < millis()) {
      dmd.clearScreen(true);

      // Draw static first row with 4-pixel gap, starting at double_Row_First_Txt_Pos + 1
      int x_pos = double_Row_First_Txt_Pos + 1;
      String first_word = "";
      for (int j = 0; j <= processed_first_text_orig.length(); j++) {
        if (j == processed_first_text_orig.length() || processed_first_text_orig.charAt(j) == ' ') {
          if (first_word.length() > 0) {
            char word_array[first_word.length() + 1];
            first_word.toCharArray(word_array, first_word.length() + 1);
            dmd.drawString(x_pos, 0, word_array, first_word.length(), GRAPHICS_NORMAL);
            x_pos += (first_word.length() * 6) + 4;
            first_word = "";
          }
        } else {
          first_word += processed_first_text_orig.charAt(j);
        }
      }

      // Draw animated second row with 5-pixel gaps
      int current_x = i;
      String current_word = "";
      for (int j = 0; j <= processed_second_text.length(); j++) {
        if (j == processed_second_text.length() || processed_second_text.charAt(j) == ' ') {
          if (current_word.length() > 0) {
            char word_array[current_word.length() + 1];
            current_word.toCharArray(word_array, current_word.length() + 1);
            dmd.drawString(current_x, 9, word_array, current_word.length(), GRAPHICS_NORMAL);
            current_x += (current_word.length() * 6) + 5;
            current_word = "";
          }
        } else {
          current_word += processed_second_text.charAt(j);
        }
      }

      if (i > -scrl_long) {
        i--;
      } else {
        break;
      }
      timer = millis();
    }
    
    // Process audio alert during display updates
    processAudioAlert();
  }
  delay(1000);
}
//________________________________________________________________________________ 

//________________________________________________________________________________VOID SETUP()
void setup(void){
  Serial.begin(115200);
  delay(1000);
  
  Serial.println();
  Serial.println("AI Parking System with High-Volume Beep Audio Feedback - Starting...");

  display_Modes.reserve(5);
  single_Row_Txt.reserve(50);
  single_Row_Txt_Orig.reserve(50);
  double_Row_First_Txt_Orig.reserve(50);
  double_Row_Second_Txt_Orig.reserve(50);
  delay(500);

  // Initialize audio system early
  Serial.println("Initializing high-volume beep audio system...");
  initializeAudioSystem();
  delay(500);

  //----------------------------------------Load data stored in flash memory.
  Serial.println("Load data stored in flash memory.");
  preferences.begin("P10_SD", false);
  
  display_Modes = preferences.getString("DM", "");
  single_Row_Txt = preferences.getString("SRT", "");
  single_Row_Txt_Orig = preferences.getString("SRTO", "");
  double_Row_First_Txt = preferences.getString("DRFT", "");
  double_Row_First_Txt_Orig = preferences.getString("DRFTO", "");
  double_Row_First_Txt_Pos = preferences.getInt("DRFTP", 0);
  double_Row_Second_Txt = preferences.getString("DRST", "");
  double_Row_Second_Txt_Orig = preferences.getString("DRSTO", "");

  Serial.print("display_Modes : ");
  Serial.println(display_Modes);
  Serial.print("single_Row_Txt : ");
  Serial.println(single_Row_Txt);
  Serial.print("single_Row_Txt_Orig : ");
  Serial.println(single_Row_Txt_Orig);
  Serial.print("double_Row_First_Txt : ");
  Serial.println(double_Row_First_Txt);
  Serial.print("double_Row_First_Txt_Orig : ");
  Serial.println(double_Row_First_Txt_Orig);
  Serial.print("double_Row_First_Txt_Pos : ");
  Serial.println(double_Row_First_Txt_Pos);
  Serial.print("double_Row_Second_Txt : ");
  Serial.println(double_Row_Second_Txt);
  Serial.print("double_Row_Second_Txt_Orig : ");
  Serial.println(double_Row_Second_Txt_Orig);

  preferences.end();
  delay(500);
  //----------------------------------------
  
  Serial.println();
  Serial.println("return the clock speed of the CPU.");
  uint8_t cpuClock = ESP.getCpuFreqMHz();
  delay(500);

  Serial.println();
  Serial.println("Timer Begin");
  timer = timerBegin(0, cpuClock, true);
  delay(500);

  Serial.println();
  Serial.println("Attach triggerScan function to our timer.");
  timerAttachInterrupt(timer, &triggerScan, true);
  delay(500);

  Serial.println();
  Serial.println("Set alarm to call triggerScan function.");
  timerAlarmWrite(timer, 300, true);
  delay(500);

  Serial.println();
  Serial.println("Start an alarm.");
  timerAlarmEnable(timer);
  delay(500);

  Serial.println();
  Serial.println("Chose the \"Arial_Black_16\" font.");
  dmd.selectFont(Arial_Black_16);

  Serial.println();
  Serial.println("Clear Screen.");
  dmd.clearScreen(true); 
  delay(500);

  timerAlarmDisable(timer);
  delay(1000);

  Serial.println();
  Serial.print("Connecting to : ");
  
  WiFi.mode(WIFI_STA);
  Serial.println(ssid);

  int time_out = 20; 
  time_out = time_out * 2;
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print(".");

    if (time_out > 0) {
      time_out--;
    } else {
      ESP.restart();
    }
    delay(500);
  }
  
  Serial.println();
  Serial.print("Successfully connected to ");
  Serial.println(ssid);
  Serial.print("IP address : ");
  Serial.println(WiFi.localIP());
  Serial.println();
 
  server.on("/", handleRoot); 
  server.on("/setText", handleSettings);

  server.begin(); 
  Serial.println();
  Serial.println("HTTP server started");
  
  if (audioSystemInitialized) {
    Serial.println("🔊 Audio system ready for high-volume beep alerts (0.5s beep + 0.5s silence)");
  } else {
    Serial.println("⚠️ Audio system initialization failed");
  }

  delay(500);

  timerAlarmEnable(timer);
  delay(500);
}
//________________________________________________________________________________

//________________________________________________________________________________VOID LOOP()
void loop(void){
  server.handleClient();  

  // Always process audio alert regardless of display mode
  processAudioAlert();

  if (display_Modes == "SR") {
    Single_Row_Display_Mode();
  }
  if (display_Modes == "DBS") {
    Double_Row_Bold_Static_Display_Mode();
  }
  if (display_Modes == "DBA") {
    Double_Row_Bold_Both_Animated_Display_Mode();
  }
  if (display_Modes == "DBM") {
    Double_Row_Bold_Mixed_Display_Mode();
  }
  
  // Small delay to prevent watchdog issues
  delay(10);
}
//________________________________________________________________________________
//<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
