import sys

dict = {
    "1":"Sum of Products",
    "2":"Product of Sums",
    "3":"Inverse Sum of Products",
    "4":"Inverse Product of Sums",
    "5":"Minimised Sum of Products (+metric)",
    "6":"Literal Minimized Product of Sums (+metric)",
    "7":"Number of Prime Implicants",
    "8":"Number of Essential Prime Implicants",
    "9":"ON-Set Minterms (Σ𝑚)",
    "10":"OFF-Set Minterms (Π𝑀)",
    "11":"Custom Command 1",
    "12":"Custom Command 2"
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
        print(item+": "+dict[item])
    print("==================================================")

def get_input(filename):
    print("File name: "+filename)


def main():
    if len(sys.argv)!=3:#wrong number of inputs
        help()
        sys.exit()
    else:
        try:
            print("Option "+ sys.argv[1]+": "+dict[sys.argv[1]])#number from 1 to 12
        except:
            print("Option number not found; please try again! Should be value from 1 to 12.")
            sys.exit()
        get_input(sys.argv[2])#get boolean function from inside file


main()
