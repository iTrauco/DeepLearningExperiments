import os
import shutil
import pygsheets
import inspect
import numpy as np
import re
import httplib2


experiment_number_file = "experiment.txt"

def find_experiment_nb(wks, name, nb_xp):
	"""
	 Using the weights file name find the experiment number in the worksheet

	 Args:
	     wks (pygsheets.Worksheet): Worksheet to look for the name
		 name (string): Name to look for
		 nb_xp (int): Current experiment number to limit the search

	 Returns:
	     int: Experiment number how contains the weights
		 int: Index which indicates if the weights are the best or not

	 Raises:
	     None: This function don't raise any exception

	"""

	# retrieve data as matrix
	names = wks.range('Q2:R{}'.format(nb_xp+1), 'matrix')

	if names:
		# find the corresponding indexes
		indexes = next(((x, y) for (x, row) in enumerate(names) for (y, cell) in enumerate(row) if cell == name), None)

	if indexes:
		return "{}Pesos Experimento {}".format("Melhores " if indexes[1] == 1 else '', indexes[0]+1)
	else:
		return "n/a"


def build_string_from_db_name(name):
	"""
	Helps on turning database name into something more human readable

	Args:
	    name (string): Database name

	Returns:
	    string: Information about database

	Raises:
	    None: This function don't raise any exception

	"""

	string_info = ''
	# get color info
	if 'RGB'.casefold() in name.casefold():
		string_info += 'RGB\n'
	elif 'Gray'.casefold() in name.casefold():
		string_info += 'Gray\n'

	# get type of approach used in the rythm extraction
	if 'Gaussian'.casefold() in name.casefold():
		string_info += 'Gaussiano\n'
	elif 'Mean'.casefold() in name.casefold():
		string_info += 'Mean\n'
	# if don't get any information about rythm
	else:
		# then it maybe not using rythm, so just return the database name
		return name

	# get the direction of the rythm
	if '_H_'.casefold() in name.casefold():
		string_info += 'Horizontal\n'
	elif '_V_'.casefold() in name.casefold():
		string_info += 'Vertical\n'
	else:
		string_info += 'Horizontal\n'

	# get the percentil position
	numbers = ''
	for i in np.arange(0.05, 1, 0.05):
		if str(i) in name:
			numbers += str(i)+' '

	# defaults to percentil 0.5 when anyone is find
	if numbers:
		string_info += numbers + '\n'
	else:
		string_info += '0.5\n'

	# get the size of filter when gaussian is used
	size_re = re.compile(r'(Size|SZ)_(\d+)', re.I)
	result = size_re.search(name)
	if result and result.group(2):
		string_info += 'Size {}\n'.format(result.group(2))

	# get the variance of filter when gaussian is used
	sigma_re = re.compile(r'(Sigma|SG)_(\d+)', re.I)
	result = sigma_re.search(name)
	if result and result.group(2):
		string_info += 'Sigma {}\n'.format(result.group(2))

	return string_info

def save_on_gsheet(secret_file, gspread_file, nb_xp, date_info, time_info,
db_info, dpout_info, nb_epochs, lr_info, bs_info, opt_info, init_info,
arch_info, best_epoch, acc_train, acc_val, loss_train, loss_val, weights_file,
bweights_file, obs=None):
	"""
	 Save information of executions directly into a Google Spreadsheet


	 Args:
	     secret_file (string): Name of file with credentials to access Google
		 			Spreadsheet API and Drive API. More information:
					https://pygsheets.readthedocs.io/en/latest/authorizing.html
		 gspread_file (string): File name of Spreadsheet on Google Drive which
		 			will be accessed and edited.
	     nb_xp (int): Number of experiment
		 date_info (string): Date already formated (eg. DD/MMM/YY hh:mm:ss)
		 time_info (string): Execution time already formated (eg. h:mm:ss.ttt)
		 db_info (string): Name of used database
		 dpout_info (float): Dropout rate used on model
		 nb_epochs (int): Number of epochs (iterations through all train set)
		 lr_info (float): Learning rate applied during training
		 bs_info (int): Batch size used during training
		 opt_info (string): Name of used optmizer
		 init_info (string): Type of initialization of model weights
		 arch_info (string): Information about architecture of used model
		 best_epoch (int): Number of epoch of best results (higher val acc)
		 acc_train (float): Train accuracy of best epoch
		 acc_val (float): Validation accuracy of best epoch
		 loss_train (float): Train loss of best epoch
		 loss_val (float): Validation loss of best epoch
		 weights_file (string): File name of weights after training process
		 bweights_file (string): File name of weights of best epoch
		 obs (string): Wildcard field to add any other relevant information

	 Returns:
	     None: This function don't have any return

	 Raises:
	     None: This function don't raise any exception

	 """

	# workaround approach to fix timeout issue
	http_client = httplib2.Http(timeout=50)
	# authenticates and open the worksheet
	gc = pygsheets.authorize(outh_file=secret_file, retries=5, http_client=http_client)
	sh = gc.open(gspread_file)
	wks = sh.sheet1

	# get parameters of this current function
	frame = inspect.currentframe()
	args, _, _, values = inspect.getargvalues(frame)

	new_row = []
	# append information to the row
	for param in args:
		if param == 'db_info':
			values[param] = build_string_from_db_name(values[param])

		if param == 'init_info':
			if values[param].endswith(('.h5', '.hdf5')):
				values[param] = find_experiment_nb(wks, values[param], nb_xp)
			elif not values[param]:
				values[param] = 'Unknown'

		if param == 'arch_info' and not values[param]:
			values[param] = 'n/a'

		if any(_str in param for _str in ['train', 'val']):
			values[param] = "{:6.4f}".format(values[param])

		if not (param == 'secret_file' or param == 'gspread_file'):
			new_row.append(str(values[param]))

	# +1 on index cause the first line have the sheet header
	wks.update_row(index=nb_xp+1, values = new_row)

	return


def save_infos(nm_script, args, init, history, best_epoch, test_score, nm_weights,
nm_weights_best, nm_plot_acc, nm_plot_loss, time_info, out_dir, obs = None,
file_name = "Experimento", use_app=None):
	"""
	Save information of execution in a text file

	Args:
	    nm_script (string): Executed script name
		args (dict): Dictionary with all arguments passed to the informed script
		init (string): Initialization method name or weights file name
		history (Hisotry): The History object returned from a fit function
		best_epoch (int): Number of epoch of best results (higher val acc)
		test_score (string): Results on testing set (when present)
		nm_weights (string): File name of weights after training process
		nm_weights_best (string): File name of weights of best epoch
		nm_plot_acc (string): Image file name of accuracy plot
		nm_plot_loss (string): Image file name of loss plot
		time_info (string[]): List containing formated strings about the start
				time, end time and elapsed time (in this order)
		out_dir (string): Output directory where all files will be coppied to.
		file_name (string): Name of folder which will contain all created files
				here. The real name will be 'file_name N' where 'N' will be the
				number present in the 'experiment.txt' file in the current
				directory. If it doesn't exists it will be created and writed
				to have the value '1'
		use_app (string): Used to pass information about training approach used
				whitin keras application


	Returns:
		None: This function don't have any return

	Raises:
		None: This function don't raise any exception

	"""

	try:
		with open(experiment_number_file, "r") as f:
			# Reading number of experiments
			nb_xp = int(f.read())
	except FileNotFoundError:
		with open(experiment_number_file, "w") as f:
			# Creating the file and writing the number of experiments
			f.write('1')
			nb_xp = 1

	# Concatenating infos in a single string to store in a file later
	info = ""

	info+= "{:*^50}\n\n".format(" About Time ")
	info+= "  Begin time: {}\n".format(time_info[0])
	info+= "    End time: {}\n".format(time_info[1])
	info+= "Elapsed time: {}\n\n".format(time_info[2])

	info+= "{:*^50}\n\n".format(" About Script and Parameters ")
	if args:
		info+= "Executed {} script with following parameters:\n".format(nm_script)
		if use_app == 'grid_ft':
			info+= "{}\n\n".format(args)
		else:
			info+= "{}\n\n".format(str(vars(args)))
		if use_app == 'tl':
			info+= "Obs: showing information about transfer learning phase\n\n"
		elif use_app == 'ft':
			info+= "Obs: showing information about fine tuning phase\n\n"
		elif use_app == 'grid_ft':
			info+= "Obs: showing information about grid fine tuning\n\n"

	info+= "{:*^50}\n\n".format(" About Created Files ")
	info+= "              File with model weights: {} \n".format(nm_weights)
	info+= "File with model weights of best epoch: {} \n".format(nm_weights_best)
	info+= "   Image plot of accuracy over epochs: {} \n".format(nm_plot_acc)
	info+= "       Image plot of loss over epochs: {} \n\n".format(nm_plot_loss)

	info+= "{:*^50}\n\n".format(" About Accuracy and Loss ")
	info+= "Best accuracy (epoch {}): \nloss: {:6.4f} acc: {:6.4f} val_loss: {:6.4f} val_acc: {:6.4f} \n".format(best_epoch+1, history.history['loss'][best_epoch], history.history['acc'][best_epoch], history.history['val_loss'][best_epoch], history.history['val_acc'][best_epoch])
	info+= "Accuracy and loss of test set: {}\n".format(test_score)
	info+= "History of accuracy and loss: \n"
	epochs = len(history.history['loss'])

	for i in range(epochs):
		info+= "Epoch {}/{}\nloss: {:6.4f} acc: {:6.4f} val_loss: {:6.4f} val_acc: {:6.4f}\n".format(i+1, epochs, history.history['loss'][i], history.history['acc'][i], history.history['val_loss'][i], history.history['val_acc'][i])

	created = False
	while(not created):
		try:
			outdir = os.path.join(out_dir, file_name+str(nb_xp))
			os.makedirs(outdir)
			created = True
			print("Folder {} succesfully created!".format(outdir))
		except FileExistsError:
			print("Folder {} already exists\n Trying to create with the next experiment number...".format(outdir))
			nb_xp+=1

	log_file = os.path.join(outdir, "log.txt")

	with open(log_file, "w") as output:
		output.write(info)

	# copying created files
	shutil.copy(nm_weights, outdir)
	shutil.copy(nm_weights_best, outdir)
	shutil.copy(os.path.join("imgs", nm_plot_acc), outdir)
	shutil.copy(os.path.join("imgs", nm_plot_loss), outdir)

	with open(experiment_number_file, "w") as output:
		# Updating number of experiments
		output.write(str(nb_xp+1))

	if use_app:
		if use_app == 'grid_ft':
			save_on_gsheet('client_secret.json', 'Experimentos Titan UCF101', nb_xp,
time_info[0], time_info[2], args['dir'], args['dropout'], args['epochs'],
args['learning_rate'], args['batch_size'], args['optimizer'], init, 'n/a', best_epoch+1,
history.history['acc'][best_epoch], history.history['val_acc'][best_epoch],
history.history['loss'][best_epoch], history.history['val_loss'][best_epoch],
nm_weights, nm_weights_best, obs)
		else:
			save_on_gsheet('client_secret.json', 'Experimentos Titan UCF101', nb_xp,
time_info[0], time_info[2], args.dir, args.dropout, args.epochs,
args.learning_rate, args.batch_size, args.optimizer, init, 'n/a', best_epoch+1,
history.history['acc'][best_epoch], history.history['val_acc'][best_epoch],
history.history['loss'][best_epoch], history.history['val_loss'][best_epoch],
nm_weights, nm_weights_best, obs)
	else:
		save_on_gsheet('client_secret.json', 'Experimentos Titan UCF101', nb_xp,
time_info[0], time_info[2], args.dir, args.dropout, args.epochs,
args.learning_rate, args.batch_size, args.optimizer, init, args.config, best_epoch+1,
history.history['acc'][best_epoch], history.history['val_acc'][best_epoch],
history.history['loss'][best_epoch], history.history['val_loss'][best_epoch],
nm_weights, nm_weights_best, obs)



	return
