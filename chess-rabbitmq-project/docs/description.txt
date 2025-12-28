# ♟️ Projet d’échecs distribué — Documentation

## Description générale

Ce projet est une application d’échecs distribuée basée sur **RabbitMQ** et une **architecture orientée événements**.
L’objectif est de faire communiquer plusieurs services indépendants autour d’une même partie d’échecs, tout en garantissant la cohérence du jeu grâce à un service central de validation.

Chaque service possède un rôle précis et communique exclusivement via RabbitMQ, ce qui permet un découplage fort, une bonne robustesse et une grande facilité d’évolution.

---

## Architecture générale

Tous les services échangent des événements via un exchange RabbitMQ commun :

- les coups sont proposés par un producteur ;
- un service de validation arbitre la partie ;
- d’autres services consomment les événements pour analyser, afficher ou sauvegarder la partie.

L’état officiel du jeu est maintenu par un seul service, ce qui évite toute incohérence.

---

## Services du projet

### 1. Producer Service (`producer.py`)

**Description**  
Le service Producer est responsable de la génération des coups à jouer.
Il utilise le moteur Stockfish pour calculer les meilleurs coups possibles et les proposer au système.

**Rôle**
- calculer les coups à l’aide de Stockfish ;
- proposer les coups via RabbitMQ ;
- attendre la validation avant de proposer un nouveau coup ;
- s’arrêter lorsque la fin de partie est annoncée.

**Remarques**
- le Producer ne vérifie jamais la légalité des coups ;
- il ne modifie pas la partie officielle ;
- il respecte strictement les décisions du service de validation.

---

### 2. Validation Service (`validation_service.py`)

**Description**  
Le service Validation est l’arbitre officiel du système.
Il maintient le plateau de vérité et décide quels coups sont acceptés ou rejetés.

**Rôle**
- maintenir le plateau officiel de la partie ;
- vérifier la légalité des coups proposés ;
- appliquer uniquement les coups légaux ;
- détecter la fin de partie (échec et mat, nulle) ;
- diffuser les événements validés.

**Remarques**
- c’est le seul service autorisé à modifier l’état officiel du jeu ;
- tous les autres services dépendent de ses décisions.

---

### 3. Analysis Service (`analysis_service.py`)

**Description**  
Le service Analysis est un service passif dédié à l’analyse de la partie en cours.
Il rejoue les coups validés et évalue chaque position à l’aide du moteur Stockfish.

**Rôle**
- rejouer la partie à partir des coups validés ;
- maintenir un plateau local indépendant ;
- analyser chaque position avec Stockfish ;
- afficher une évaluation claire et lisible.

**Interprétation des scores**
- score positif : avantage pour les Blancs ;
- score négatif : avantage pour les Noirs ;
- score proche de zéro : position équilibrée ;
- mat détecté : annonce du camp gagnant et du nombre de coups restants.

**Remarques**
- le service ne joue aucun coup ;
- il ne modifie jamais la partie officielle ;
- plusieurs services d’analyse peuvent être lancés en parallèle.

---

### 4. Spectator Service (`spectator_service.py`)

**Description**  
Le service Spectator permet d’afficher graphiquement la partie en cours.
Il offre une visualisation en temps réel du plateau à partir des coups validés.

**Rôle**
- afficher le plateau d’échecs ;
- rejouer les coups validés ;
- montrer la position actuelle de la partie.

**Remarques**
- le service est entièrement passif ;
- il peut être redémarré sans perturber la partie ;
- il permet une meilleure compréhension du déroulement du jeu.

---

### 5. Storage Service (`storage_service.py`)

**Description**  
Le service Storage est chargé de la sauvegarde des données de la partie.

**Rôle**
- enregistrer les coups joués ;
- conserver l’historique des parties ;
- permettre une exploitation ultérieure des données.

---

## Technologies utilisées

- Langage : Python
- Middleware de messagerie : RabbitMQ
- Moteur d’échecs : Stockfish

**Bibliothèques principales**
- pika : communication RabbitMQ
- python-chess : gestion du plateau et des coups
- matplotlib : affichage graphique

---

## Perspectives d’amélioration

- rendre le jeu interactif pour permettre à un joueur humain de jouer contre l’IA ;
- proposer une interface graphique ou web pour la saisie des coups ;
- afficher les meilleurs coups recommandés par Stockfish ;
- permettre à l’utilisateur de choisir le niveau de difficulté de l’IA ;
- ajouter un mode Humain vs IA ou IA vs IA.

Ces évolutions renforceraient l’aspect ludique et pédagogique du projet, tout en démontrant la flexibilité de l’architecture distribuée.
