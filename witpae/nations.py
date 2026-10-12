"""Nation codes shared by the aircraft (@284) and ship class (@26) tables."""

NATIONS = {1: "IJA", 2: "IJN", 4: "USN", 5: "USA", 7: "Aus", 8: "NZ", 9: "UK", 10: "French",
           11: "Dutch", 13: "Soviet", 18: "Canada"}
# Guessed; shown with a trailing "?".
GUESSED_NATIONS = {12: "China", 14: "India"}


def label(value, verified, guessed):
    if value in verified:
        return verified[value]
    if value in guessed:
        return guessed[value] + "?"
    return str(value)


def nation_label(nation_id):
    return label(nation_id, NATIONS, GUESSED_NATIONS)
