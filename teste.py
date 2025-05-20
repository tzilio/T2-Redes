import random

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
SUITS = ["♥", "♠", "♦", "♣"]

def create_deck():
    return [f"{rank}{suit}" for suit in SUITS for rank in RANKS]

def deal_hands(deck):
    random.shuffle(deck)
    return [deck[i*13:(i+1)*13] for i in range(4)]

def card_value(card):
    rank = card[:-1]
    return RANKS.index(rank)

def suit_of(card):
    return card[-1]

def print_hand(hand):
    for c in hand:
        print(f"{c:>4}", end="")
    print()
    for i in range(len(hand)):
        print(f"{i:>4}", end="")
    print("\n")

def choose_cards_to_pass(hand):
    print("Sua mão:")
    print_hand(hand)
    chosen = set()
    while len(chosen) < 3:
        try:
            idx = int(input(f"Escolha o índice da carta {len(chosen)+1}/3 para passar: "))
            if idx < 0 or idx >= len(hand) or idx in chosen:
                print("Índice inválido ou repetido.")
                continue
            chosen.add(idx)
        except ValueError:
            print("Entrada inválida.")
    selected = [hand[i] for i in sorted(chosen, reverse=True)]
    for i in sorted(chosen, reverse=True):
        hand.pop(i)
    return selected

def bot_choose_cards_to_pass(hand):
    selected = random.sample(range(len(hand)), 3)
    cards = [hand[i] for i in sorted(selected, reverse=True)]
    for i in sorted(selected, reverse=True):
        hand.pop(i)
    return cards

def pass_phase(hands):
    passed = [None] * 4

    # Seleciona as 3 cartas que cada jogador irá passar
    passed[0] = choose_cards_to_pass(hands[0])
    for i in range(1, 4):
        passed[i] = bot_choose_cards_to_pass(hands[i])

    # Entrega as cartas ao jogador da direita (sentido horário)
    for i in range(4):
        receiver = (i + 1) % 4
        hands[receiver].extend(passed[i])

    # Reordena as mãos após receber as cartas
    for h in hands:
        h.sort(key=lambda c: (SUITS.index(c[-1]), RANKS.index(c[:-1])))

    print("\nCartas passadas com sucesso!\n")

def play_trick(players, trick_num):
    lead = None
    trick = []
    print(f"\nTrick #{trick_num + 1}")
    for i, hand in enumerate(players):
        if i == 0:
            while True:
                print("Sua mão:")
                print_hand(hand)
                try:
                    idx = int(input("Selecione o índice da carta a jogar: "))
                    if idx < 0 or idx >= len(hand):
                        print("Índice inválido.")
                        continue
                    play = hand[idx]
                    if trick_num == 0 and play != "2♣":
                        print("Você deve iniciar com 2♣ na primeira rodada.")
                        continue
                    if lead and suit_of(play) != lead and any(suit_of(c) == lead for c in hand):
                        print(f"Você deve seguir o naipe {lead}.")
                        continue
                    hand.pop(idx)
                    trick.append((i, play))
                    lead = suit_of(play)
                    break
                except ValueError:
                    print("Entrada inválida.")
        else:
            valid = [c for c in hand if suit_of(c) == lead] if lead else hand
            if not valid:
                valid = hand
            play = random.choice(valid)
            hand.remove(play)
            trick.append((i, play))
            print(f"Jogador {i} joga {play}")
            if lead is None:
                lead = suit_of(play)
    winner = max((c for c in trick if suit_of(c[1]) == lead), key=lambda x: card_value(x[1]))
    print(f"Jogador {winner[0]} venceu a rodada.")
    return winner[0], [card for _, card in trick]

def score_trick(trick):
    score = 0
    for card in trick:
        if card.endswith("♥"):
            score += 1
        elif card == "Q♠":
            score += 13
    return score

def main():
    deck = create_deck()
    hands = deal_hands(deck)
    for h in hands:
        h.sort(key=lambda c: (SUITS.index(c[-1]), RANKS.index(c[:-1])))

    # PASSAGEM
    pass_phase(hands)

    scores = [0, 0, 0, 0]
    starter = next(i for i, h in enumerate(hands) if "2♣" in h)
    current = starter

    # Rotaciona as mãos para que o jogador esteja sempre na posição 0
    player_hand = hands[starter]
    bot_hands = hands[starter+1:] + hands[:starter]

    for t in range(13):
        all_hands = [player_hand] + bot_hands
        winner_offset, trick_cards = play_trick(all_hands, t)
        trick_score = score_trick(trick_cards)
        real_winner = (starter + winner_offset) % 4
        scores[real_winner] += trick_score

        # Ajusta ordem das mãos para próxima rodada
        starter = real_winner
        player_hand = all_hands[winner_offset]
        bot_hands = all_hands[winner_offset+1:] + all_hands[:winner_offset]

    print("\nPontuação Final:")
    for i, s in enumerate(scores):
        print(f"Jogador {i}: {s} pontos")

if __name__ == "__main__":
    main()
