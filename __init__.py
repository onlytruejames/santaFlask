from flask import Flask, render_template, request, redirect, session
import itsdangerous, random, uuid, json

#Replace [location] with the location of the secrets.json file
secretFile = open("[location]", "r")
secrets = json.load(secretFile)
secretFile.close()

#encryption stuff for later
USS = itsdangerous.URLSafeSerializer(secrets["USS1"], secrets["USS2"])

def encrypt(data):
    return USS.dumps(json.dumps(data))

def decrypt(data):
    return json.loads(USS.loads(data))

#flask code below
app = Flask(__name__)
app.secret_key = secrets["session"]

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/generate/', defaults={"people": None})
@app.route('/generate/<people>')
def generate(people):
    #ensure that there's people
    people = request.args.get('people')
    if not people:
        return redirect('/?fail=1')
    
    #tidy up names
    people = people.split(",")
    for person in range(len(people)):
        if people[person][0] == " ":
            people[person] = people[person][1:]
    
    #We need a list of people which can be viewed by the users without them being able to identify who they're paired with
    #We need a list of people who are in the real shuffled order
    #Enter public and pricate people
    publicPeople = [person for person in people]
    privatePeople = [people.pop(random.randint(0, len(people)-1)) for i in range(len(people))]
    #people is now a list of names in a random order

    #include identifier to store in session to guarantee nobody peeks
    id = str(uuid.uuid4())

    #now to encode into one string and pass to the share page
    key = encrypt({"publicPeople": publicPeople, "privatePeople": privatePeople, "id": id})
    return redirect(f'/share?key={key}')

@app.route('/share/', defaults={"key": None})
@app.route('/share/<key>')
def share(key):
    #share page - seperate from the generating one because if the page is reloaded nothing happens 
    host = request.root_url
    key = request.args.get('key')
    #check to see if the key exists, is normal, or is malformed
    if not key:
        #does not exist
        return redirect('/?fail=1')
    data = decrypt(key)
    try:
        assert type(data) == dict
    except:
        #best case it's a mistake
        #worst case there's some sort of link injection going on. not really much you can do with it but nevertheless
        return redirect('/?fail=1')
    
    return render_template('share.html', url=f'{host}/view?key={key}')

@app.route('/view/', defaults={"key": None})
@app.route('/view/<key>')
def view(key):
    #get the encrypted data
    key = request.args.get('key')
    if not key:
        return redirect('/?fail=1')
    data = decrypt(key)
    id = data["id"]
    people = data["publicPeople"]

    #ensure that the user is in fact not peeking
    try:
        sessionStatus = session[id]
    except:
        session[id] = False
        sessionStatus = False
    if sessionStatus:
        #peeker
        return render_template('finished.html')
    #not peeker
    return render_template('view.html', key=key, people=people)

@app.route('/query/', methods=["POST"])
def query():
    #try and decode the JSON info from the fetch thing on view.html
    try:
        info = request.get_json()
        key = info["key"]
        gifter = info["person"]
        data = decrypt(key)
    except:
        #unless it breaks
        return "Error", 400
    
    #ensure that the user isn't peeking
    id = data["id"]
    try:
        sessionStatus = session[id]
    except:
        session[id] = False
    if sessionStatus:
        return "Forbidden", 403
    
    #find the index of the gifter in the shuffled array
    people = data["privatePeople"]
    if not gifter in people:
        return "None", 404
    index = False
    for p in range(len(people)):
        if people[p] == gifter:
            index = p
    
    #given that privatePeople is a shuffled version of the people, this means that there is a single random cyclic permutation in this array
    #as a result, returning the next person in the array will result in the gifter gifting to a different person who nobody else is gifting to
    #so there are no smaller loops than *everybody* in an unknown order
    #this is horrifically overengineered innit
    people.append(people.pop(0))
    gifted = people[index]
    session[id] = True
    return {"gifter": gifter, "gifted": gifted}

if __name__ == "__main__":
    app.run()