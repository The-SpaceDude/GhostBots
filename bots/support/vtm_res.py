import random

"""
# soak roll: 1s cancel, but no critfail (pg 306)
# dmg  roll: 1s cancel, but no critfail. Commonly houseruled with no canceling
# atk  roll: 1s cancel and can critfail

# crit failing: no successes and 1s present in the roll. if there are more 1s than successes, it's still a normal fail! (v20)
"""

# failcancel: 0: no canceling, 1: canceling, but no critfails, 2: full canceling and critfailing, 3: revised critfailing
# spec: specialization effect for 10s
# cancel_high: cancel successes from lowest (false), or highest (True). only matters when specializations apply. DEFAULT ?
# spec_reroll: true: reroll dei 10, false: doppio successo DEFAULT FALSE

def decider(roll_sorted, difficulty, failcancel = 2, spec = False, cancel_high = True, spec_reroll = False):
    md = -1 # will contain the index of the first success
    for i in range(0, len(roll_sorted)):
        if roll_sorted[i] >= difficulty:
            md = i
            break
    if md == -1:
        md = len(roll_sorted)
    successes = roll_sorted[md:] # filter successes out of the roll
    count_success = len(successes)
    crit_fails = roll_sorted.count(1)
    if failcancel > 0: # and crit_fails > 0
        if failcancel == 2 and  crit_fails > 0 and count_success == 0: # critfail
            return -1, roll_sorted
        elif failcancel == 3 and  crit_fails > count_success: # revised critfail
            return -1, roll_sorted
        else: #just cancel
            if cancel_high and crit_fails > 0:
                successes = successes[:-crit_fails]
            else:
                successes = successes[crit_fails:]
            count_success = len(successes)
    tens = successes.count(10)
    if spec:
        if spec_reroll:
            additional = 0
            for i in range(0, tens):
                if random.randint(1, 10)>= difficulty:
                    additional += 1
            return count_success+additional, roll_sorted
        else:
            return count_success+tens, roll_sorted
    else:
        return count_success, roll_sorted

def roller(ndice, nfaces, diff, cancel = True, spec = False):
    roll_raw = sorted(list(map(lambda x: random.randint(1, nfaces), range(0, ndice))))
    roll_sorted = sorted(roll_raw)
    md = -1 # will contain the index of the first success
    for i in range(0, len(roll_sorted)):
        if roll_sorted[i] >= diff:
            md = i
            break
    if md == -1: # nessun successo
        md = len(roll_sorted) 
    successes = roll_sorted[md:] # filter successes out of the roll
    count_success = len(successes)
    crit_fails = roll_sorted.count(1)
    canceled = 0
    if cancel:
        if crit_fails > 0 and count_success == 0: # critfail
            return -1, roll_raw, 0
        elif crit_fails > count_success: # critfail drammatico
            return -2, roll_sorted, count_success
        else: #just cancel
            if crit_fails > 0:
                canceled = crit_fails
                successes = successes[:-crit_fails]
            count_success = len(successes)
    tens = successes.count(10)
    if spec:
        return count_success+tens, roll_sorted, canceled
    else:
        return count_success, roll_sorted, canceled


def rollpool(dicepool, difficulty, failcancel = 2, spec = False, cancel_high = False, spec_reroll = False):
    if dicepool == 0:
        print("0 dice")
    roll_raw = sorted(list(map(lambda x: random.randint(1, 10), range(0, dicepool))))
    return decider(roll_raw, difficulty, failcancel, spec, cancel_high, spec_reroll)


if __name__ == "__main__":
    for i in range(0, 100):
        print(rollpool(10, 8, 2, False, True, False))
    test_rolls = [[1],
                  [3, 6, 6, 8],
                  [6],
                  [5, 7, 8],
                  [7],
                  [5, 7],
                  [8, 9],
                  [5],
                  [2, 4, 4, 5, 6, 6, 6, 6, 8, 9],
                  [5, 5, 6, 10],
                  [1, 4, 8, 8, 9],
                  [3],
                  [4, 4, 8],
                  [1, 1, 3, 3, 3, 4, 6, 7, 8, 9],
                  [2, 3, 6],
                  [3, 4, 5, 6, 10],
                  [7, 8, 10],
                  [1, 2, 7, 7, 9, 10, 10],
                  [3, 5, 8, 8, 10],
                  [1, 3, 9],
                  [1, 1, 4, 4, 5, 6, 9, 9, 10],
                  [1, 6, 9, 9, 10],
                  [1, 1, 3, 3, 4, 6, 8, 9, 9],
                  [1, 1, 1, 1, 2, 6, 6],
                  [1, 3, 7, 8],
                  [8],
                  [1, 3, 8],
                  [3, 8, 10],
                  [5, 7, 9],
                  [2, 3, 3, 5, 5, 6, 7, 10],
                  [1, 2, 4, 6, 6, 8, 8, 9],
                  [2, 5, 5, 8, 9, 10],
                  [2, 4, 6, 6, 7, 8],
                  [5, 8, 8, 8, 9, 10, 10, 10],
                  [3, 3, 5, 6, 8, 8, 9],
                  [1, 2, 3, 7, 7, 7, 7, 7, 8, 10],
                  [1, 1, 2, 5, 9, 10],
                  [1, 1, 4, 5, 6, 10],
                  [3, 8],
                  [7, 9],
                  [1, 10],
                  [1, 2, 4, 4, 4, 6, 9, 10],
                  [1, 2, 3, 4, 7, 10],
                  [1, 1, 2, 2, 2, 2, 4, 9, 9],
                  [5, 10],
                  [1, 1, 5, 6, 9, 9, 9, 10],
                  [7, 8],
                  [1, 4, 5, 6, 7, 8, 10],
                  [1, 5, 7, 9, 10]]
    # fc 0, nospec, highcancel, anyreroll
    assert decider([1, 1, 1, 1, 2, 6, 6], 6, 0, False, True, False)[0] == 2
    assert decider([1, 1, 1, 1, 2, 6, 6], 6, 0, False, False, False)[0] == 2
    assert decider([1, 1, 1, 1, 2, 6, 6], 6, 0, False, False, True)[0] == 2
    assert decider([1, 1, 1, 1, 2, 6, 6], 6, 0, False, True, True)[0] == 2
    for dice in range(0, 10):
        for tens in range(0, dice):
            for ones in range(0, dice-tens):
                for successes in range(0, dice-tens-ones):
                    for difficulty in range(3, 10):
                        roll = sorted([10]*tens+[1]*ones+[random.randint(difficulty, 9) for i in range(0, successes)]+[random.randint(2, difficulty-1) for i in range(0, dice-ones-tens-successes)])
                        assert decider(roll, difficulty, 3, False, True, False)[0] == max(-1, tens+successes-ones)
                        # 2
                        if successes+tens > 0: # botch not possible
                            assert decider(roll, difficulty, 2, False, True, False)[0] >= 0
                            if successes+tens <= ones:
                                assert decider(roll, difficulty, 2, False, True, False)[0] == 0
                            else:
                                assert decider(roll, difficulty, 2, False, True, False)[0] == tens+successes-ones
                        # 1 cancel no botch
                        
