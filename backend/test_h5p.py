import json
import zipfile
import io
from h5p_generator import H5PGenerator

def test_h5p_generation():
    print("Starte H5P Generierungstest...")
    
    mock_data = {
        "title": "Test Grammatik: Simple Past",
        "diagnostic": {
            "questions": [
                {
                    "question": "Was ist die Past Tense Form von 'go'?",
                    "options": ["went", "goed"],
                    "correct": 0
                },
                {
                    "question": "Was ist die Past Tense Form von 'buy'?",
                    "options": ["buyed", "bought"],
                    "correct": 1
                }
            ]
        },
        "level_a": {
            "title": "Level A - Grundlagen",
            "text": "Yesterday I *went* (go) to school. I *bought* (buy) an apple."
        },
        "level_b": {
            "title": "Level B - Vertiefung",
            "text": "Yesterday I *went* to the local market and *bought* a fresh red apple."
        }
    }

    # Generate H5P zip bytes
    h5p_bytes = H5PGenerator.create_h5p_zip(mock_data)
    
    # Verify zip content
    zip_file = zipfile.ZipFile(io.BytesIO(h5p_bytes))
    file_list = zip_file.namelist()
    
    print("\nErstellte Dateien im H5P-Paket:")
    for f in file_list:
        print(f" - {f}")
        
    assert "h5p.json" in file_list, "h5p.json fehlt im ZIP!"
    assert "content/content.json" in file_list, "content/content.json fehlt im ZIP!"
    
    # Read content.json and check title
    content_data = json.loads(zip_file.read("content/content.json").decode("utf-8"))
    assert content_data["branchingScenario"]["startScreen"]["startScreenTitle"] == "Test Grammatik: Simple Past"
    
    # Check that branching questions and blanks exist
    nodes = content_data["branchingScenario"]["content"]
    assert len(nodes) == 5, f"Erwartete 5 Knoten (3 Fragen, 2 Level), erzeugt wurden: {len(nodes)}"
    
    print("\nKnoten im Branching Scenario:")
    for node in nodes:
        print(f" Library = {node['type']['library']}")
        
    print("\nTest erfolgreich abgeschlossen!")

if __name__ == "__main__":
    test_h5p_generation()
