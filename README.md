# cREST
Command line tool for scenario-based interaction with RESTful services. **It is in progress, so if you are interested in such tool, please don't hesistate to leave your opinion and share your thoughts**

## Installation
**cREST** is a single python script. Place it anywhere you want but please make sure that it would have a read/write access to `crest.conf` directory nearby.

## Configuration
There are the plenty of built-in commands which provide you with the ability to perform different common operations with RESTful services, such as making requests, posting the data, concatenating and escaping query strings and so on. There are also some number of basic commands like entering the data from keyboard or showing it on the screen.

But the key feature of cREST is the writing your own commands specific to the RESTful service you use. All user-defined commands are lists of other commands, either built-in or user-defined, evaluated in order they were defined. To define the new commands, you must create `*.crest` file in `crest.conf` directory with the following content:
```
function some-function arg1-name arg2-name arg3-name ...
command1 command-arg1 command-arg2 ...
command2 command-arg1 ...
...
function another-function
...
```
All `crest.conf/*.crest` files are loaded on startup and functions defined in these files become available.
### Syntax
* Every command name, argument name and argument value must not contain spaces or tabulation and newline characters
* You can surround keywords, commands, argument names and values with any number of spaces and tabulation characters if you want to.
* If an argument value has to contain one of these characters, wrap the entire argument in a single quotes like this:
```
command-which-accepts-multiline-argument 'line1
line2
line3'
```
* If the argument value has to contain either `'` iself or `\` character, use `\'` and `\\` instead.
* Every command and command definition must be located on the single line with all its' arguments. If you would like to break this rule for readability purposes, use backslash in the end of each wrapped line, like this:
```
command \
  argument1 \
  argument2
```
* Use construction `${variable-name}` for substitution at run time. You can nest it: `${variable-containing-prefix-${variable-containing-name}`. It is possible to substitute commands.
* If the variable contains either valid `json` or `xml`, you can extend variable name with the path. For example, if the variable `var` contains the following json:
```
{
  "nodes": [
    {"name": "one"},
    {"name": "two"}
  ]
}
```
Then `${var.nodes[1].name}` would be substituted with `two`

### Variables
* All variables, even those which are command arguments are global. You must not worry about their scope, passing between command etc., but you have to choose names unique enough to not clash between them. The preferred way to do that is to use prefixes for important variables e.g. `my-service-login`, `project-hash` but you are free to name variables as you like, it's up to you, until you request a merge from your fork.
* There are no variable types, they all contain just plain text, but if this text is a valid `json` or `xml`, some additional abilities are provided as mentioned above.

### Special variables
Some variables has the special meaning and are meant to be changed by the respective commands:
* `url` contains the url address of the last HTTP request made by request commands (`get`, `post`, `delete` etc.).
* `header-*` is a group of variables which a treated as request headers by request commands, e.g. setting `header-Accept` actually adds `Accept` header to all subsequent HTTP requests.
* `response.code` contains the last HTTP response code.
* `response.header-*` contains the last HTTP response headers.
* `response.body` contains the last HTTP response body.
* `!*` - all variables which names start with exclamation mark are stored into `crest.conf/__store.crest` file. That means that every restart, values for these variables is restored.
