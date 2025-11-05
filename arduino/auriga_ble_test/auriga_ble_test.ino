#include <MeAuriga.h>

#define BUZZER_PIN 45
#define LED_RING_PIN 44

#define AURIGARINGLEDNUM 12
#define RINGALLLEDS 0

MeBuzzer buzzer;

MeRGBLed led_ring(0, AURIGARINGLEDNUM);


unsigned long currentTime = 0;
bool debugMode = false;

void setup() {
  Serial.begin(115200);
  buzzer.setpin(BUZZER_PIN);
  led_ring.setpin(LED_RING_PIN);
}

void loop() {
  currentTime = millis();
  stateManager(currentTime);
  communicationTask();
}

// Tâche servant à communiquer des données
void communicationTask() {
}

// Événement qui se déclenche lorsqu'il y a réception de données via le port série
void serialEvent() {
  static String receivedData = "";

  if (!Serial.available()) return;

  receivedData = Serial.readStringUntil('\n');
  parseData(receivedData);
}

/**
  Fonction servant à analyser les données reçues.
  "parse" veut dire analyser
*/
void parseData(String& receivedData) {
  bool isFromBLE = false;  // Indicateur de source des données

  if (receivedData.length() >= 2) {
    // Vérifier si les deux premiers octets sont 0xFF55 (BLE)
    if ((uint8_t)receivedData[0] == 0xFF && (uint8_t)receivedData[1] == 0x55) {
      isFromBLE = true;
      // Supprimer les deux premiers octets
      receivedData.remove(0, 2);
    }
    // Vérifier si les deux premiers caractères sont "!!" (Moniteur Série)
    else if (receivedData.startsWith("!!")) {
      // Supprimer les deux premiers caractères
      receivedData.remove(0, 2);
    } else {
      // En-tête non reconnue
      Serial.print(F("Données non reconnues : "));
      Serial.println(receivedData);
      return;
    }
  } else {
    Serial.print(F("Données trop courtes : "));
    Serial.println(receivedData);
    return;
  }

  // Afficher les données reçues si le mode débogage est activé
  if (debugMode) {
    Serial.print(F("Reçu : "));
    Serial.println(receivedData);
    Serial.print(F("Source : "));
    Serial.println(isFromBLE ? F("BLE") : F("Moniteur Série"));
  }

  // Découpage de la commande et des paramètres
  int firstComma = receivedData.indexOf(',');

  if (firstComma == -1) {
    // Pas de virgule, donc c'est une commande sans paramètres
    handleCommand(receivedData);
  } else {
    // Il y a des paramètres
    String command = receivedData.substring(0, firstComma);
    String params = receivedData.substring(firstComma + 1);
    handleCommandWithParams(command, params);
  }
}

// Fonction pour gérer une commande sans paramètres
void handleCommand(String command) {
  // Utilisation d'un switch pour les commandes sans paramètres
  char cmd = command[0];
  switch (cmd) {
    case 'b':  // Commande "BEEP"
      Serial.println(F("Commande BEEP reçue - exécuter le bip"));
      commandBeep();
      break;

    case 'd':  // Commande pour basculer le mode débogage
      debugMode = !debugMode;
      Serial.print(F("Mode débogage : "));
      Serial.println(debugMode ? F("activé") : F("désactivé"));
      break;

    default:
      Serial.print(F("Commande inconnue sans paramètres : "));
      Serial.println(command);
      break;
  }
}

// Fonction pour gérer une commande avec paramètres
void handleCommandWithParams(String command, String params) {
  char cmd = command[0];
  switch (cmd) {
    case 'f':  // Commande "FORWARD"
      Serial.print(F("Commande FORWARD reçue avec paramètres : "));
      Serial.println(params);

      commandForward(params);
      break;

    case 'l':  // Commande "LIGHT" pour définir la couleur de l'anneau LED
      Serial.print(F("Commande LIGHT reçue avec paramètres : "));
      Serial.println(params);
      commandLight(params);
      break;

    default:
      Serial.print(F("Commande inconnue avec paramètres : "));
      Serial.print(command);
      Serial.print(F(", "));
      Serial.println(params);
      break;
  }
}

void stateManager(unsigned long ct) {
}

#pragma region COMMANDES

void ledAction(int r, int g, int b) {
  led_ring.setColor(r, g, b);
  led_ring.show();
}

void ledAction(int idx, int r, int g, int b) {
  // Mettre à jour la couleur de toutes les LEDs de l'anneau
  if (idx == 0) {
    led_ring.setColor(r, g, b);
  } else {
    led_ring.setColorAt(idx, r, g, b);
  }

  led_ring.show();
}

void commandBeep() {
  buzzer.tone(1000, 500);  // Par exemple, bip sur la broche 45 pendant 500ms
}

void commandLight(String params) {
  int commaCount = countCharOccurrences(params, ',');

  // Vérifie le nombre de paramètres en comptant les virgules
  if (commaCount == 2) {
    // Trois paramètres (r, g, b) pour définir toute la couleur de l'anneau
    int r = params.substring(0, params.indexOf(',')).toInt();
    params = params.substring(params.indexOf(',') + 1);
    int g = params.substring(0, params.indexOf(',')).toInt();
    int b = params.substring(params.indexOf(',') + 1).toInt();

    ledAction(r, g, b);  // Appel pour affecter l'ensemble de l'anneau
  } else if (commaCount == 3) {
    // Quatre paramètres (idx, r, g, b) pour définir une LED spécifique
    int idx = params.substring(0, params.indexOf(',')).toInt();
    params = params.substring(params.indexOf(',') + 1);
    int r = params.substring(0, params.indexOf(',')).toInt();
    params = params.substring(params.indexOf(',') + 1);
    int g = params.substring(0, params.indexOf(',')).toInt();
    int b = params.substring(params.indexOf(',') + 1).toInt();

    ledAction(idx, r, g, b);  // Appel pour affecter une LED spécifique
  } else {
    Serial.println(F("Commande lumière invalide"));
  }
}

void commandForward(String params) {
  // paramètre
  Serial.print(F("Paramètre : "));
  Serial.println(params);
  // Ajouter le code pour traiter la commande FORWARD avec ses paramètres
}

#pragma endregion

#pragma region HELPERS
int countCharOccurrences(const String& str, char ch) {
  int count = 0;
  for (int i = 0; i < str.length(); i++) {
    if (str[i] == ch) {
      count++;
    }
  }
  return count;
}
#pragma endregion