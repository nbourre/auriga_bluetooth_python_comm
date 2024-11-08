#include <MeAuriga.h>

unsigned long currentTime = 0;
bool debugMode = false;

void setup() {
  Serial.begin(115200);
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

  receivedData = Serial.readString();
  parseData(receivedData);
}

/**
  Fonction servant à analyser les données reçues.
  "parse" veut dire analyser
*/
void parseData(String& receivedData) {
  bool isFromBLE = false;  // Indicateur de source des données

  if (receivedData.length() >= 2) {
    // Vérifier si les deux premiers octets sont 0xFF00 (BLE)
    if ((uint8_t)receivedData[0] == 0xFF && (uint8_t)receivedData[1] == 0x00) {
      isFromBLE = true;
      // Supprimer les deux premiers octets
      receivedData.remove(0, 2);
    }
    // Vérifier si les deux premiers caractères sont "!!" (Moniteur Série)
    else if (receivedData.startsWith("!!")) {
      // Supprimer les deux premiers caractères
      receivedData.remove(0, 2);
    }
    else {
      // En-tête non reconnue
      Serial.print(F("Données non reconnues : "));
      Serial.println(receivedData);
      return;
    }
  }
  else {
    Serial.print(F("Données trop courtes : "));
    Serial.println(receivedData);
    return;
  }

  // Afficher les données reçues si le mode débogage est activé
  if (debugMode) {
    Serial.print("Reçu : ");
    Serial.println(receivedData);
    Serial.print("Source : ");
    Serial.println(isFromBLE ? "BLE" : "Moniteur Série");
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
      Serial.println("Commande BEEP reçue - exécuter le bip");
      // Ajouter le code pour exécuter le bip
      break;

    case 'd':  // Commande pour basculer le mode débogage
      debugMode = !debugMode;
      Serial.print("Mode débogage : ");
      Serial.println(debugMode ? "activé" : "désactivé");
      break;

    default:
      Serial.print("Commande inconnue sans paramètres : ");
      Serial.println(command);
      break;
  }
}

// Fonction pour gérer une commande avec paramètres
void handleCommandWithParams(String command, String params) {
  char cmd = command[0];
  switch (cmd) {
    case 'f':  // Commande "FORWARD"
      Serial.print("Commande FORWARD reçue avec paramètres : ");
      Serial.println(params);

      // Découpage des paramètres
      int commaIndex;
      while ((commaIndex = params.indexOf(',')) != -1) {
        String param = params.substring(0, commaIndex);
        Serial.print("Paramètre : ");
        Serial.println(param);
        params = params.substring(commaIndex + 1);
      }
      // Dernier paramètre
      Serial.print("Dernier paramètre : ");
      Serial.println(params);
      // Ajouter le code pour traiter la commande MOVE avec ses paramètres
      break;

    default:
      Serial.print("Commande inconnue avec paramètres : ");
      Serial.print(command);
      Serial.print(", ");
      Serial.println(params);
      break;
  }
}

void stateManager(unsigned long ct) {
}
