#!/usr/bin/python2
import socket
import json
import os
import random
import sys
from socket import error as SocketError
import errno
sys.path.append("../..")
import src.game.game_constants as game_consts
from src.game.character import *
from src.game.gamemap import *

# Game map that you can use to query 
gameMap = GameMap()


MELEE_STUN = 1
RANGE_STUN = 14
RANGE_ARMOR = 4
SELF_ARMOR = 15
ROOT = 13
BACKSTAB = 11
HEAL = 3
BURST = 0
SPRINT = 12
WARRIOR_FLAG = False
ARCHER_FLAG = False

# --------------------------- SET THIS IS UP -------------------------
teamName = "pwd"
# ---------------------------------------------------------------------

# Set initial connection data
def initialResponse():
# ------------------------- CHANGE THESE VALUES -----------------------
    return {'TeamName': teamName,
            'Characters': [
                {"CharacterName": "Paladin",
                 "ClassId": "Assassin"},
                {"CharacterName": "Warrior",
                 "ClassId": "Assassin"},
                {"CharacterName": "Druid",
                 "ClassId": "Assassin"},
            ]}
# ---------------------------------------------------------------------
# HELPER FUNCTIONS

def worthSprint(ourCharacter, target): #check if a sprint is worth it
    distance = getLateralDistance(ourCharacter.position, target.position)
    return distance > 1

def getLateralDistance(position1, position2): #check distances laterally
    return abs(position1[0] - position2[0]) + abs(position1[1] - position2[1])

def getClass(team, classId):
    character = filter(lambda c:c.classId==classId, team)
    if len(character)==0:
        character = None
    else:
        character = character[0]
    return character

def getPriorityTarget(character, enemy_team):
    if len(enemy_team)==0:
        return None
    
    if ARCHER_FLAG:
        closest = enemy_team[0]
        lowestDist = 100
        for enemy in enemy_team:
            dist = getLateralDistance(character.position, enemy.position)
            if dist<lowestDist:
                lowestDist = dist
                closest = enemy
        return closest
    else:
        priorities = ["Druid", "Assassin", "Archer", "Sorcerer", "Wizard", "Enchanter", "Warrior", "Paladin"]
        for p in priorities:
            for e in enemy_team:
                if e.classId==p:
                    return e
        return enemy_team[0]

def cast(actions, character, target, ability):
    actions.append({
                     "Action": "Cast",
                     "CharacterId": character.id,
                     "TargetId": target.id,
                     "AbilityId": int(ability)
    })

def attack(actions, character, target):
    actions.append({
                    "Action": "Attack",
                    "CharacterId": character.id,
                    "TargetId": target.id
    })

def move(actions, character, target):
    actions.append({
                "Action": "Move",
                "CharacterId": character.id,
                "TargetId": target.id
    })

def getStunnedRooted(character):
    stunned = False
    rooted = False
    # check condition (rooted, stunned, silenced, etc)
    for debuff in character.debuffs:
        attribute = debuff['Attribute']
        if attribute == "Stunned":
            stunned = True
        elif attribute == "Rooted":
            rooted = True
    return stunned, rooted

def move_pos(actions, character, pos):
    actions.append({
        "Action": "Move",
        "CharacterId": character.id,
        "Location": pos
    })

def clearMove(positions, enemies):
    #print positions
    for pos in positions:
        for en in enemies:
            if pos == en.position and (pos in positions):
                positions.remove(pos)
    if len(positions)==0: 
        return None
    else:
        return positions[0]
turn = -1
attack_flag = False


# Determine actions to take on a given turn, given the server response
def processTurn(serverResponse):
    global turn
    global WARRIOR_FLAG
    global ARCHER_FLAG
    global attack_flag
    print " ---- "
    turn += 1
# --------------------------- CHANGE THIS SECTION -------------------------
    # Setup helper variables
    actions = []
    myteam = []
    enemyteam = []
    # Find each team and serialize the objects
    for team in serverResponse["Teams"]:
        if team["Id"] == serverResponse["PlayerInfo"]["TeamId"]:
            for characterJson in team["Characters"]:
                character = Character()
                character.serialize(characterJson)
                myteam.append(character)
        else:
            for characterJson in team["Characters"]:
                character = Character()
                character.serialize(characterJson)
                enemyteam.append(character)
# ------------------ You shouldn't change above but you can ---------------




    enemyalive = filter(lambda c:not c.is_dead(), enemyteam)
    myalive = filter(lambda c:not c.is_dead(), myteam)
    
    healmap = {}
    armormap = {}
    for enemy in enemyalive:
        #print enemy.casting
        if enemy.id not in armormap:
            armormap[enemy.id] = 0
        if enemy.id not in healmap:
            healmap[enemy.id] = 0
        if enemy.casting:
            targetId = enemy.casting['TargetId']
            if enemy.casting['AbilityId']==HEAL and enemy.casting['CurrentCastTime']==0:
                #print "healing..."
                #print (targetId in healmap)
                if targetId in healmap:
                    healmap[targetId] += 250
                else:
                    healmap[targetId] = 250
            if enemy.casting['AbilityId']==SELF_ARMOR and enemy.casting['CurrentCastTime']==0:
                if targetId in armormap:
                    armormap[targetId] += 30
                else:
                    armormap[targetId] = 30
            if enemy.casting['AbilityId']==RANGE_ARMOR and enemy.casting['CurrentCastTime']==0:
                if targetId in armormap:
                    armormap[targetId] += 40
                else:
                    armormap[targetId] = 40
    
    #all archers case
    numarcher = len(filter(lambda c:c.classId=='Archer', enemyalive))
    if numarcher == 3 or (numarcher==2 and len(enemyalive)==3) or ARCHER_FLAG:
        ARCHER_FLAG = True
        print "ANTI-ARCHER MODE!"
        
    #all warriors case. We get rekt so just try to tie
    numwarrior = len(filter(lambda c:c.classId=='Warrior', enemyalive))
    if numwarrior == 3 or WARRIOR_FLAG:
        WARRIOR_FLAG = True
        # nooooo
        print "ANTI-WARRIOR MODE!"
        for character in myalive:
            stunned, rooted = getStunnedRooted(character)
            # Am I stunned? cast burst
            burst_cd = character.abilities[BURST]
            if stunned and character.casting is None:
                if burst_cd == 0:
                    cast(actions, character, character, BURST)
                    print "bursting to remove crowd-control"
                    continue
                else:
                    continue
            elif attack_flag:
                #print "extra attack"
                target = getPriorityTarget(character, enemyalive)
                if target==None:
                    return {
                        'TeamName': teamName,
                        'Actions': actions
                    }
                if character.in_range_of(target, gameMap):
                    backstab_cd = character.abilities[BACKSTAB]
                    if backstab_cd==0:
                        cast(actions, character, target, BACKSTAB)
                    else:
                        # RUN FOR OUR LIVES!!
                        adj = gameMap.get_valid_adjacent_pos(character.position)
                        position = clearMove(adj, enemyteam)
                        if position == None:
                            #RIP. move random
                            move_pos(actions, character, adj[0])
                        elif position != character.position:
                            move_pos(actions, character, position)
                attack_flag = False
            # if our burst isn't ready or if we have more than enemy
            elif burst_cd != 0 or len(myalive)>len(enemyalive):
                # RUN FOR OUR LIVES!!
                print "running!"
                adj = gameMap.get_valid_adjacent_pos(character.position)
                position = clearMove(adj, enemyteam)
                if position == None:
                    #RIP. move random
                    move_pos(actions, character, adj[0])
                elif position != character.position:
                    move_pos(actions, character, position)
            elif burst_cd == 0 and len(myalive)<=len(enemyalive):
                # attack if we are tied/losing... and burst is ready
                target = getPriorityTarget(character, enemyalive)
                if target==None:
                    return {
                        'TeamName': teamName,
                        'Actions': actions
                    }
                if character.in_range_of(target, gameMap):
                    backstab_cd = character.abilities[BACKSTAB]
                    if backstab_cd==0:
                        cast(actions, character, target, BACKSTAB)
                        attack_flag = True
                    else:
                        # RUN FOR OUR LIVES!!
                        adj = gameMap.get_valid_adjacent_pos(character.position)
                        position = clearMove(adj, enemyteam)
                        if position == None:
                            #RIP. move random
                            move_pos(actions, character, adj[0])
                        elif position != character.position:
                            move_pos(actions, character, position)
                else:
                    move(actions, character, target)
                    print "Moving to warriors"
        return {
            'TeamName': teamName,
            'Actions': actions
        }



    # Normal case
    else:
        target = getPriorityTarget(character, enemyalive)
        
        if target==None:
            return {
                'TeamName': teamName,
                'Actions': actions
            }
        target_new_hp = target.attributes.health+healmap[target.id]
        #print target_new_hp
        for character in myteam:
            #print "character: "+character.name
            if character.is_dead():
                continue

            stunned, rooted = getStunnedRooted(character)
            #print character.debuffs
            #print stunned, rooted
            # Am I stunned? cast burst
            if stunned and character.casting is None:
                willcast = False
                burst_cd = character.abilities[BURST]
                if burst_cd == 0:
                    cast(actions, character, character, BURST)
                    #print "busting to remove crowd-control"
                    willcast = True
                    continue
                else:
                    continue
            
            willcast = False
            # If I am in range, else move towards target
            if character.in_range_of(target, gameMap):
                willcast = False
                backstab_cd = character.abilities[BACKSTAB]
                #TODO take into account enemy queued heals
                if backstab_cd == 0: #if we can, backstab these mofos
                    #but only if regular attack won't kill...
                    if target_new_hp > (110-target.attributes.armor-armormap[target.id]): 
                        cast(actions, character, target, BACKSTAB)
                        willcast = True
                        #print "backstabbing target "+target.name
                        target_new_hp -= (200-target.attributes.armor-armormap[target.id])
                        #print target_new_hp
                    else:
                        print "microoptimization - avoiding using backstab"
                if not willcast:
                    attack(actions, character, target)
                    #print "attacking target "+target.name
                    target_new_hp -= (110-target.attributes.armor-armormap[target.id])
                    #print target_new_hp
                if target_new_hp <= 0:
                    # if we killed it, get a new target
                    #print "will kill: "+target.name
                    #print "actual hp:", target.attributes.health
                    print "microoptimization - retargetting to new enemy. Prev enemy hp: ", target_new_hp
                    enemyalive.remove(target)
                    target = getPriorityTarget(character, enemyalive)
                    if target == None:
                        return {
                            'TeamName': teamName,
                            'Actions': actions
                        }
                    target_new_hp = target.attributes.health + healmap[target.id]
                    #print "new enemy "+target.name+" hp:",target_new_hp
            else: # Not in range, move towards
                #if we can sprint, sprint
                #dont need to check for cast time
                #TODO - optimize sprint times better?
                
                #TODO look for other targets in range? If they exist, dont bother bursting
                if rooted:
                    willcast = False
                    burst_cd = character.abilities[BURST]
                    if burst_cd == 0:
                        cast(actions, character, character, BURST)
                        #print "busting to remove crowd-control"
                        willcast = True
                        continue
                    else:
                        continue
                sprint_cd = character.abilities[SPRINT]
                #print "It is worth sprinting: " + str(worthSprint(character, target))
                if sprint_cd == 0 and worthSprint(character, target): #if we can sprint
                    #print "we are sprinting"
                    cast(actions, character, character, SPRINT)
                else:
                    move(actions, character, target)
    # Send actions to the server
    return {
        'TeamName': teamName,
        'Actions': actions
    }












# ---------------------------------------------------------------------

# Main method
# @competitors DO NOT MODIFY
if __name__ == "__main__":
    # Config
    conn = ('localhost', 1337)
    if len(sys.argv) > 2:
        conn = (sys.argv[1], int(sys.argv[2]))

    # Handshake
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(conn)

    # Initial connection
    s.sendall(json.dumps(initialResponse()) + '\n')

    # Initialize test client
    game_running = True
    members = None

    # Run game
    try:
        data = s.recv(1024)
        while len(data) > 0 and game_running:
            value = None
            if "\n" in data:
                data = data.split('\n')
                if len(data) > 1 and data[1] != "":
                    data = data[1]
                    data += s.recv(1024)
                else:
                    value = json.loads(data[0])

                    # Check game status
                    if 'winner' in value:
                        game_running = False

                    # Send next turn (if appropriate)
                    else:
                        msg = processTurn(value) if "PlayerInfo" in value else initialResponse()
                        s.sendall(json.dumps(msg) + '\n')
                        data = s.recv(1024)
            else:
                data += s.recv(1024)
    except SocketError as e:
        if e.errno != errno.ECONNRESET:
            raise  # Not error we are looking for
        pass  # Handle error here.
    s.close()
