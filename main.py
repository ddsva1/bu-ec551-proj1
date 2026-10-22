import sys

dict = {"1": "Sum of Products",
    "2": "Product of Sums",
    "3": "Inverse Sum of Products",
    "4": "Inverse Product of Sums",
    "5": "Minimised Sum of Products (+metric)",
    "6": "Literal Minimized Product of Sums (+metric)",
    "7": "Number of Prime Implicants",
    "8": "Number of Essential Prime Implicants",
    "9": "ON-Set Minterms (Σ𝑚)",
    "10": "OFF-Set Minterms (Π𝑀)",
    "11": "Custom Command 1",
    "12": "Custom Command 2"
 }

def help():
    print("Structure of Command Line input:")
    print("py main.py number-from-1-to-12 relative-address-of-file-with-boolean-function")
    print("--------------------------------------------------")
    print("Available input function types:")
    print("Sum of Products")
    print("--------------------------------------------------")
    print("Available Options:")
    for item in dict:
        print(item, ": ", dict[item])
    print("==================================================")

def one(x,info, filename):
    print("SOP: ",x)
    f = open("output.txt", "w")

    #module setup and i/o wires
    f.write("module x(\n")
    f.write("   output reg XOUT,\n")
    counter = 0
    while counter< len(info[0])-1:
        f.write("   input wire "+info[0][counter]+",\n")
        counter = counter+1
    f.write("   input wire "+info[0][counter]+"\n")
    f.write(");\n")

    #internal wires setup
    counter = 0
    andwires = []
    while counter <len(info[1]):
        f.write("   wire and"+str(counter)+";\n")
        andwires.append("and"+str(counter))
        counter = counter+1
    print("temp wires: "+str(andwires))

    #creating and gates
    andx = 0
    for item in info[1]:
        andlist = item[0]
        counter = 1
        if (len(item) == 1):
            andlist = andlist + ", 1'b1"
        elif (len(item)==2 and andlist == "~"):
            andlist = andlist + item[1]+", 1'b1"
        else:
            if andlist == "~":
                andlist = andlist+item[1]
                counter = counter+1
            while counter<len(item):

                if item[counter] == "~":
                    andlist = andlist+", ~"+item[counter+1]
                    counter = counter+2
                elif item[counter]!= "~":
                    andlist = andlist+", "+item[counter]
                    counter = counter +1
            
        f.write("   and("+andwires[andx]+", "+andlist+");\n")
        andx = andx+1
    
    #creating or gate\
    orgate = andwires[0]
    counter = 1
    if (len(info[1]) == 1):
                orgate = orgate + ", 1'b1"
    else:
        while counter < len(info[1]):
            orgate = orgate + ", " +andwires[counter]
            counter = counter + 1
    f.write("   or(XOUT,"+orgate+");\n")



    #ending module
    f.write("endmodule")


def two(x):
    print("POS: not done yet")

def three(x):
    print("ISOP: not done yet")

def four(x):
    print("IPS: not done yet")

def five(x):
    print("MSP: not done yet")

def six(x):
    print("LMSP: not done yet")

def seven(x):
    print("NPI: not done yet")

def eight(x):
    print("NEPI: not done yet")

def nine(x):
    print("ONSM: not done yet")

def ten(x):
    print("OFFSM: not done yet")

def eleven(x):
    print("CC1: not done yet")

def twelve(x):
    print("CC2: not done yet")

def zero(x):
    list_of_prods = x.split('+')
    print("products summed in given expression: ",list_of_prods)
    varset = []
    for item in list_of_prods:
        for item2 in list(item):
            if (item2 not in varset) and (item2 != "~"):
                varset.append(item2)
    print("variables in expression: ",varset)
    return [varset, list_of_prods]


def main():
    if len(sys.argv)!=3:
        help()
        exit
    else:
        try:
            task = sys.argv[1]
            print(task+": "+ dict[task])
            filename = sys.argv[2]
            print("File name entered: "+filename)
        except:#not number from 1 to 12
            print("please check number entered - should be value from 1 to 12.")
            help()
            exit
        try:
            file = open(filename, "r")
            x = file.read()
            print("function inside file: ", x)
            file.close()
        except:
            print ("please check file name")
            help()
            quit
        info = zero(x)
        if task == "1":
            one(x, info, filename)
        elif task == "2":
            two(x)
        elif task == "3":
            three(x)
        elif task == "4":
            four(x)
        elif task == "5":
            five(x)
        elif task == "6":
            six(x)
        elif task == "7":
            seven(x)
        elif task == "8":
            eight(x)
        elif task == "9":
            nine(x)
        elif task == "10":
            ten(x)
        elif task == "11":
            eleven(x)
        elif task == "12":
            twelve(x)
                
                






main()
