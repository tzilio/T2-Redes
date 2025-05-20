#!/usr/bin/env python3

# --- PARTE 1: IMPORTS, CONSTANTES E ESTADO GLOBAL

import socket, sys, time, json, random
from ring_network import *

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
SUITS = ["♥", "♠", "♦", "♣"]
RANK_INDEX = {r: i for i, r in enumerate(RANKS)}
SUIT_INDEX = {s: i for i, s in enumerate(SUITS)}

state = {
    "hand": [],
    "pass_done": False,
    "received_pass": [],
    "received_from": False,
    "token_sent": False,
    "NEXT_ADDR": None
}

game_state = {
    "current_trick": [],
    "round_number": 0,
    "starter_id": None,
    "playing": False,
    "player_points": [0]*4
}

# --- PARTE 2: UTILITARIOS DE CARTAS E IMPRESSAO
def sort_hand(cards):
    return sorted(cards, key=lambda c: (SUIT_INDEX[c[-1]], RANK_INDEX[c[:-1]]))

def print_hand(cards):
    cards = sort_hand(cards)
    print("   " + " ".join(f"{c:>3}" for c in cards))
    print("   " + " ".join(f"{i:>3}" for i in range(len(cards))))

def send_packet(sock, pkt, addr):
    sock.sendto(json.dumps(pkt).encode(), addr)


# --- PARTE 3: DISTRIBUICAO DE CARTAS
def deal_cards(sock, next_addr):
    deck = [rank + suit for suit in SUITS for rank in RANKS]
    random.shuffle(deck)
    for i in range(4):
        packet = {"type": "DEAL", "origin": 0, "target": i, "cards": deck[i*13:(i+1)*13]}
        send_packet(sock, packet, next_addr)


# --- PARTE 4: ESCOLHA DE CARTAS (PASS/PLAY)
def choose_cards_to_pass():
    print("\nEscolha 3 cartas para passar (índices separados por espaço):")
    print_hand(state["hand"])
    while True:
        try:
            idxs = list(map(int, input("> ").split()))
            if len(idxs) == 3 and all(0 <= i < len(state["hand"]) for i in idxs):
                selected = [state["hand"][i] for i in idxs]
                for card in selected:
                    state["hand"].remove(card)
                return selected
        except: pass
        print("Entrada inválida.")

def choose_play():
    print("\nSua vez de jogar. Escolha o índice da carta:")
    print_hand(state["hand"])
    while True:
        try:
            idx = int(input("> "))
            if 0 <= idx < len(state["hand"]):
                return sort_hand(state["hand"])[idx]
        except: pass
        print("Índice inválido.")

# --- PARTE 5: HANDLERS PRINCIPAIS (DEAL, PASS, SHOW_HAND, EXIT)
def handle_deal(pkt, node_id, sock, local_addr):
    if pkt["target"] == node_id:
        state["hand"] = pkt["cards"]
        print(f"[Node {node_id}] RECEBEU DEAL — mão inicial:")
        print_hand(state["hand"])

    if pkt["origin"] == node_id and not state["token_sent"] and node_id == 0:
        inject_token(sock, local_addr)
        state["token_sent"] = True
    else:
        send_packet(sock, pkt, state["NEXT_ADDR"])

def handle_pass(pkt, node_id, sock):
    if pkt["to"] == node_id:
        state["received_pass"] = pkt["cards"]
        state["received_from"] = True

        if not state["pass_done"]:
            selected = choose_cards_to_pass()
            send_packet(sock, {
                "type": "PASS", "from": node_id,
                "to": (node_id + 1) % 4,
                "cards": selected
            }, state["NEXT_ADDR"])
            state["pass_done"] = True

        if state["pass_done"] and state["received_from"]:
            print(f"[Node {node_id}] RECEBEU PASS de {pkt['from']}: {pkt['cards']}")
            state["hand"].extend(state["received_pass"])
            if node_id == 3:
                send_packet(sock, {"type": "SHOW_HAND", "origin": node_id}, state["NEXT_ADDR"])
    else:
        send_packet(sock, pkt, state["NEXT_ADDR"])

def handle_show_hand(pkt, node_id, sock):
    print(f"[Node {node_id}] MÃO ATUAL:")
    print_hand(state["hand"])
    if pkt["origin"] != node_id:
        send_packet(sock, pkt, state["NEXT_ADDR"])
    else:
        print(f"[Node {node_id}] Fim da exibição das mãos.")

    if "2♣" in state["hand"]:
        game_state["starter_id"] = node_id
        send_packet(sock, {
            "type": "TOKEN", "phase": "play",
            "starter": node_id, "round": 1,
            "trick": []
        }, state["NEXT_ADDR"])

def handle_exit(node_id, data, sock):
    send_packet(sock, data, state["NEXT_ADDR"])
    print(f"[Node {node_id}] RECEBEU EXIT — encerrando.")

# --- PARTE 6: HANDLERS DE JOGO (TOKEN E ROUND_SUMMARY)
def handle_token(pkt, node_id, sock):
    phase = pkt.get("phase", "pass")

    if phase == "pass" and not state["pass_done"]:
        selected = choose_cards_to_pass()
        send_packet(sock, {
            "type": "PASS", "from": node_id,
            "to": (node_id + 1) % 4,
            "cards": selected
        }, state["NEXT_ADDR"])
        state["pass_done"] = True

    elif phase == "play":
        game_state["playing"] = True
        game_state["starter_id"] = pkt["starter"]
        game_state["round_number"] = pkt["round"]
        game_state["current_trick"] = pkt["trick"]

        turno_id = (game_state["starter_id"] + len(game_state["current_trick"])) % 4

        if len(game_state["current_trick"]) < 4:
            if turno_id == node_id:
                card = choose_play()
                state["hand"].remove(card)
                game_state["current_trick"].append((node_id, card))
                print(f"[Node {node_id}] JOGOU: {card}")
                send_packet(sock, {
                    "type": "TOKEN", "phase": "play",
                    "starter": game_state["starter_id"],
                    "round": game_state["round_number"],
                    "trick": game_state["current_trick"]
                }, state["NEXT_ADDR"])
            else:
                send_packet(sock, pkt, state["NEXT_ADDR"])
        else:
            print(f"\n=== Rodada {game_state['round_number']} encerrada ===")
            print(f"Jogador que começou: {game_state['starter_id']}")
            for pid, card in game_state["current_trick"]:
                print(f"Jogador {pid} jogou {card}")

            winner = determine_trick_winner(game_state["current_trick"])
            send_packet(sock, {
                "type": "ROUND_SUMMARY",
                "starter": game_state["starter_id"],
                "trick": game_state["current_trick"],
                "winner": winner,
                "origin": node_id
            }, state["NEXT_ADDR"])

            # próxima rodada
            send_packet(sock, {
                "type": "TOKEN", "phase": "play",
                "starter": winner,
                "round": game_state["round_number"] + 1,
                "trick": []
            }, state["NEXT_ADDR"])

def handle_round_summary(pkt, node_id, sock):
    print(f"\n=== Rodada {pkt['round'] if 'round' in pkt else game_state['round_number']} encerrada ===")
    print(f"Jogador que começou: {pkt['starter']}")
    for pid, card in pkt["trick"]:
        print(f"Jogador {pid} jogou {card}")
    print(f"Jogador {pkt['winner']} venceu a rodada\n===========================\n")

    if pkt["origin"] != node_id:
        send_packet(sock, pkt, state["NEXT_ADDR"])


# --- PARTE 7: DETERMINACAO DO VENCEDOR
def determine_trick_winner(trick):
    lead_suit = trick[0][1][-1]
    valid = [(pid, c) for pid, c in trick if c[-1] == lead_suit]
    return max(valid, key=lambda x: RANK_INDEX[x[1][:-1]])[0]

# --- PARTE 8: MAIN
def main():
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        print(f"Uso: {sys.argv[0]} <node_id (0-3)>")
        sys.exit(1)

    node_id = int(sys.argv[1])
    if not 0 <= node_id < 4:
        print("node_id inválido. Deve ser 0, 1, 2 ou 3.")
        sys.exit(1)

    local_addr = NODES[node_id]
    state["NEXT_ADDR"] = NODES[(node_id + 1) % 4]
    sock = setup_socket(local_addr)
    print(f"[Node {node_id}] em {local_addr}, next → {state['NEXT_ADDR']}")

    if node_id == 0:
        time.sleep(1)
        deal_cards(sock, state["NEXT_ADDR"])

    handlers = {
        "DEAL": lambda pkt: handle_deal(pkt, node_id, sock, local_addr),
        "PASS": lambda pkt: handle_pass(pkt, node_id, sock),
        "SHOW_HAND": lambda pkt: handle_show_hand(pkt, node_id, sock),
        "TOKEN": lambda pkt: handle_token(pkt, node_id, sock),
        "ROUND_SUMMARY": lambda pkt: handle_round_summary(pkt, node_id, sock),
        "EXIT": lambda pkt: handle_exit(node_id, json.dumps(pkt).encode(), sock),
    }

    while True:
        data, _ = sock.recvfrom(4096)
        try:
            pkt = json.loads(data.decode())
        except json.JSONDecodeError:
            continue

        pkt_type = pkt.get("type")
        handler = handlers.get(pkt_type)
        if handler:
            handler(pkt)
            if pkt_type == "EXIT":
                break
        else:
            send_packet(sock, pkt, state["NEXT_ADDR"])

    print(f"[Node {node_id}] saiu.")

if __name__ == "__main__":
    main()
