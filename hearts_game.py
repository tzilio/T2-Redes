#!/usr/bin/env python3
import socket
import sys
import time
import json
import random
from ring_network import *

# Ordem de exibição: ranks 2→A, naipes: copas, espadas, ouro, paus
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
SUITS = ["♥", "♠", "♦", "♣"]
RANK_INDEX = {r: i for i, r in enumerate(RANKS)}
SUIT_INDEX = {s: i for i, s in enumerate(SUITS)}

# Variáveis compartilhadas entre funções
hand = []
token_sent = [False]
pass_done = [False]
received_pass = []
received_from = [False]
NEXT_ADDR = None

current_trick = []       # Cartas jogadas na rodada atual
round_number = [0]       # Número da rodada (vai até 13)
starter_id = [None]      # Quem iniciou a rodada
playing = [False]        # Se estamos na fase de jogo

player_points = [0] * 4


def sort_hand(cards):
    return sorted(cards, key=lambda card: (
        SUIT_INDEX[card[-1]],
        RANK_INDEX[card[:-1]]
    ))

def print_hand(cards):
    formatted = [f"{c:>3}" for c in cards]
    indices = [f"{i:>3}" for i in range(len(cards))]
    print("   " + " ".join(formatted))
    print("   " + " ".join(indices))

def deal_cards(sock, next_addr):
    deck = [rank + suit for suit in SUITS for rank in RANKS]
    random.shuffle(deck)
    hands = [deck[i*13:(i+1)*13] for i in range(4)]
    print("[Node 0] Embaralhando e enviando DEALs…")
    for target_id, cards in enumerate(hands):
        packet = {
            "type": "DEAL",
            "origin": 0,
            "target": target_id,
            "cards": cards
        }
        sock.sendto(json.dumps(packet).encode(), next_addr)

def count_points(trick):
    total = 0
    for _, card in trick:
        if card[-1] == "♥":
            total += 1
        elif card == "Q♠":
            total += 13
    return total


def inject_token(sock, local_addr):
    token_pkt = {"type": "TOKEN"}
    sock.sendto(json.dumps(token_pkt).encode(), local_addr)
    print("[Node 0] Token INJETADO — começa o PASS aqui.")

def handle_deal(packet, node_id, sock, local_addr, next_addr):
    global hand, token_sent
    origin = packet["origin"]
    target = packet["target"]
    cards = packet["cards"]

    if target == node_id:
        hand[:] = cards
        print(f"[Node {node_id}] RECEBEU DEAL — mão inicial:")
        print_hand(sort_hand(hand))

    if origin != node_id:
        sock.sendto(json.dumps(packet).encode(), next_addr)
    else:
        if node_id == 0 and not token_sent[0]:
            inject_token(sock, local_addr)
            token_sent[0] = True

def choose_cards_to_pass():
    global hand
    ordered_hand = sort_hand(hand)
    print("\nEscolha 3 cartas para passar (índices separados por espaço):")
    print_hand(ordered_hand)

    while True:
        try:
            indexes = list(map(int, input("> ").split()))
            if len(indexes) == 3 and all(0 <= i < len(ordered_hand) for i in indexes):
                selected = [ordered_hand[i] for i in indexes]
                print(f"Você escolheu para passar: {selected}")
                # Remover as cartas corretas da mão original
                for card in selected:
                    hand.remove(card)
                return selected
        except ValueError:
            pass
        print("Entrada Inválida. Tente Novamente.")


def handle_token(packet, node_id, sock):
    global playing, round_number, starter_id, current_trick

    phase = packet.get("phase", "pass")

    if phase == "pass":
        if not pass_done[0]:
            selected = choose_cards_to_pass()
            to = (node_id + 1) % 4
            packet = {
                "type": "PASS",
                "from": node_id,
                "to": to,
                "cards": selected
            }
            sock.sendto(json.dumps(packet).encode(), NEXT_ADDR)
            pass_done[0] = True

    elif phase == "play":
        playing[0] = True
        starter_id[0] = packet["starter"]
        round_number[0] = packet["round"]
        current_trick = packet["trick"]

        if len(current_trick) < 4:
            if (starter_id[0] + len(current_trick)) % 4 == node_id:
                card = choose_play()
                hand.remove(card)
                current_trick.append((node_id, card))

                print(f"[Node {node_id}] JOGOU: {card}")

                new_token = {
                    "type": "TOKEN",
                    "phase": "play",
                    "starter": starter_id[0],
                    "round": round_number[0],
                    "trick": current_trick
                }
                sock.sendto(json.dumps(new_token).encode(), NEXT_ADDR)
            else:
                sock.sendto(json.dumps(packet).encode(), NEXT_ADDR)
        else:
            print(f"\n=== Rodada {round_number[0]} encerrada ===")
            print(f"Jogador que começou: {starter_id[0]}")
            for pid, card in current_trick:
                print(f"Jogador {pid} jogou {card}")

            winner = determine_trick_winner(current_trick)

            summary = {
                "type": "ROUND_SUMMARY",
                "starter": starter_id[0],
                "trick": current_trick,
                "winner": winner,
                "origin": node_id
            }
            sock.sendto(json.dumps(summary).encode(), NEXT_ADDR)

            # inicia próxima rodada
            next_round = {
                "type": "TOKEN",
                "phase": "play",
                "starter": winner,
                "round": round_number[0] + 1,
                "trick": []
            }
            time.sleep(1)
            sock.sendto(json.dumps(next_round).encode(), NEXT_ADDR)


def handle_round_summary(packet, node_id, sock):
    starter = packet["starter"]
    trick = packet["trick"]
    winner = packet["winner"]
    origin = packet["origin"]

    print(f"\n=== Rodada {round_number[0]} encerrada ===")
    print(f"Jogador que começou: {starter}")
    for pid, card in trick:
        print(f"Jogador {pid} jogou {card}")
    print(f"🏆 Jogador {winner} venceu a rodada")
    print("===========================\n")

    if origin != node_id:
        sock.sendto(json.dumps(packet).encode(), NEXT_ADDR)


def handle_pass(packet, node_id, sock):
    global hand, pass_done, received_pass, NEXT_ADDR, received_from
    frm = packet["from"]
    to = packet["to"]
    cards = packet["cards"]

    if to == node_id:
        received_pass[:] = cards
        received_from[0] = True

        if not pass_done[0]:
            selected = choose_cards_to_pass()
            next_to = (node_id + 1) % 4
            pass_packet = {
                "type": "PASS",
                "from": node_id,
                "to": next_to,
                "cards": selected
            }
            sock.sendto(json.dumps(pass_packet).encode(), NEXT_ADDR)
            pass_done[0] = True

        if pass_done[0] and received_from[0]:
            print(f"[Node {node_id}] RECEBEU PASS de {frm}: {cards}")
            hand.extend(received_pass)

            # Se for o último jogador, inicia SHOW_HAND
            if node_id == 3:
                show_pkt = {
                    "type": "SHOW_HAND",
                    "origin": node_id
                }
                sock.sendto(json.dumps(show_pkt).encode(), NEXT_ADDR)
    else:
        sock.sendto(json.dumps(packet).encode(), NEXT_ADDR)



def handle_show_hand(packet, node_id, sock):
    global NEXT_ADDR
    origin = packet["origin"]

    print(f"[Node {node_id}] MÃO ATUAL:")
    print_hand(sort_hand(hand))

    if origin != node_id:
        sock.sendto(json.dumps(packet).encode(), NEXT_ADDR)
    else:
        print(f"[Node {node_id}] Fim da exibição das mãos.")

    # Inicia a fase de jogo
    if "2♣" in hand:
        starter_id[0] = node_id
        token_pkt = {
            "type": "TOKEN",
            "phase": "play",
            "starter": node_id,
            "round": 1,
            "trick": []
        }
        sock.sendto(json.dumps(token_pkt).encode(), NEXT_ADDR)


def choose_play():
    print("\nSua vez de jogar. Escolha o índice da carta:")
    print_hand(sort_hand(hand))
    while True:
        try:
            idx = int(input("> "))
            if 0 <= idx < len(hand):
                return sort_hand(hand)[idx]
        except ValueError:
            pass
        print("Índice inválido.")


def determine_trick_winner(trick):
    lead_suit = trick[0][1][-1]  # naipe da primeira carta
    valid_plays = [
        (pid, card) for (pid, card) in trick if card[-1] == lead_suit
    ]
    # Compara os ranks apenas das cartas do mesmo naipe
    winner = max(valid_plays, key=lambda x: RANK_INDEX[x[1][:-1]])
    return winner[0]



def handle_exit(node_id, data, sock):
    global NEXT_ADDR
    sock.sendto(data, NEXT_ADDR)
    print(f"[Node {node_id}] RECEBEU EXIT — encerrando.")

def main():
    global NEXT_ADDR
    # Validação de argumentos
    if len(sys.argv) != 2:
        print(f"Uso: {sys.argv[0]} <node_id>")
        sys.exit(1)

    node_id = int(sys.argv[1])
    if not 0 <= node_id < 4:
        print("node_id inválido. Deve ser 0, 1, 2 ou 3.")
        sys.exit(1)

    LOCAL_ADDR = NODES[node_id]
    NEXT_ADDR = NODES[(node_id + 1) % 4]
    sock = setup_socket(LOCAL_ADDR)
    print(f"[Node {node_id}] em {LOCAL_ADDR}, next → {NEXT_ADDR}")

    if node_id == 0:
        time.sleep(1)
        deal_cards(sock, NEXT_ADDR)

    while True:
        data, _ = sock.recvfrom(4096)
        try:
            pkt = json.loads(data.decode())
        except json.JSONDecodeError:
            continue

        pkt_type = pkt.get("type")

        match pkt_type:
            case "EXIT":
                handle_exit(node_id, data, sock)
                break
            case "DEAL":
                handle_deal(pkt, node_id, sock, LOCAL_ADDR, NEXT_ADDR)
            case "TOKEN":
                handle_token(pkt, node_id, sock)
            case "PASS":
                handle_pass(pkt, node_id, sock)
            case "SHOW_HAND":
                handle_show_hand(pkt, node_id, sock)
            case _:
                sock.sendto(data, NEXT_ADDR)

    print(f"[Node {node_id}] saiu.")

if __name__ == "__main__":
    main()
