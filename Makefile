.PHONY: run clean help

# Chemins vers les fichiers
INPUT_DIR = input
OUTPUT_DIR = output
INPUT_FILE = $(INPUT_DIR)/fiab.csv
OUTPUT_FILE = $(OUTPUT_DIR)/importSite-fiabilisation-with-osm.csv

# Cible par défaut : exécuter le script
run:
	@echo "Exécution du script avec $(INPUT_FILE) comme entrée et $(OUTPUT_FILE) comme sortie."
	python main.py $(INPUT_FILE) $(OUTPUT_FILE)

# Cible pour nettoyer le fichier généré
clean:
	@echo "Suppression du fichier généré $(OUTPUT_FILE)"
	-rm -f $(OUTPUT_FILE)

# Cible d'aide pour rappeler les commandes disponibles
help:
	@echo "Utilisation :"
	@echo "  make run    => Exécute le script main.py"
	@echo "  make clean  => Supprime le fichier de sortie"
	@echo "  make help   => Affiche cette aide"
