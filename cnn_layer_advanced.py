import numpy as np

# vectorization of the computation
# will add batch normalization
# will add dropout
# will add padding to convolutional layer

def relu(x):
	return np.maximum(x, 0)

def sigmoid(x):
	return 1 / (1 + np.exp(-x))

def tanh(x):
	return np.tanh(x)

def linear(x):
	return x

def drelu(grad_a, act):
	grad_a[act <= 0] = 0
	return grad_a

def dsigmoid(grad_a, act):
	return np.multiply(grad_a, act - np.square(act))

def dtanh(grad_a, act):
	return np.multiply(grad_a, 1 - np.square(act))

def dlinear(grad_a, act):
	return grad_a

def img2col(x, k_size, stride):
	col_matrix = []
	batch, channel, height, width = x.shape
	for i in range(0, height-k_size+1, stride):
		for j in range(0, width-k_size+1, stride):
			#convert kernel size squre into row
			col_matrix.append(x[:, :, i:i+k_size, j:j+k_size].reshape([batch,-1]))
	return np.array(col_matrix).reshape(-1, channel*k_size*k_size)
	
def col2img(col, in_shape, out_shape, k_size, stride):
	in_c, in_h, in_w = in_shape
	out_c, out_h, out_w = out_shape
	batch_size = col.shape[0]//out_h//out_w
	img = np.zeros((batch_size, in_c, in_h, in_w))
	for row in range(col.shape[0]):
		b_idx = row%batch_size
		pos = row//batch_size
		i = pos//out_w*stride
		j = pos%out_w*stride
		img[b_idx, :, i:i+k_size, j:j+k_size] += col[row].reshape([in_c, k_size, k_size])
	return img

class Layer(object):
	def __init__(self, has_param):
		self.act_funcs = {'ReLU': relu, 'Sigmoid': sigmoid, 'Tanh': tanh, "Linear": linear}
		self.dact_funcs = {'ReLU': drelu, 'Sigmoid': dsigmoid, 'Tanh': dtanh, "Linear": dlinear}
		self.gradient_funcs = {'Adam':self.adam, "SGD": self.sgd}
		self.learning_rate = 1e-2
		self.weight_decay = 1e-4
		self.has_param = has_param

	def forward(self, x):
		pass

	def gradient(self, grad_act, act):
		pass

	def backward(self, grad_type):
		if self.has_param:
			self.regularize()
			self.gradient_funcs[grad_type]()

	def regularize(self):
		self.w *= (1 - self.weight_decay)
		self.b *= (1 - self.weight_decay)

	def adam(self):
		beta1 = 0.9
		beta2 = 0.999
		eps = 1e-8
		alpha = self.learning_rate
		self.mom_w = beta1 * self.mom_w + (1 - beta1) * self.grad_w
		self.cache_w = beta2 * self.cache_w + (1 - beta2) * np.square(self.grad_w)
		self.w -= alpha * self.mom_w / (np.sqrt(self.cache_w) + eps)
		self.mom_b = beta1 * self.mom_b + (1 - beta1) * self.grad_b
		self.cache_b = beta2 * self.cache_b + (1 - beta2) * np.square(self.grad_b)
		self.b -= alpha * self.mom_b / (np.sqrt(self.cache_b) + eps)

	def sgd(self):
		self.w -= self.learning_rate * self.grad_w
		self.b -= self.learning_rate * self.grad_b

class Conv(Layer):
	def __init__(self, in_shape, k_size, k_num, act_type, stride=1):
		super(Conv, self).__init__(has_param=True)
		self.act_func = self.act_funcs[act_type]
		self.dact_func = self.dact_funcs[act_type]
		self.in_shape = in_shape
		channel, height, width = in_shape
		self.k_size = k_size
		self.w = np.random.randn(channel*k_size*k_size, k_num)
		self.b = np.random.randn(1,k_num)

		self.mom_w = np.zeros_like(self.w)
		self.cache_w = np.zeros_like(self.w)
		self.mom_b = np.zeros_like(self.b)
		self.cache_b = np.zeros_like(self.b)

		self.out_shape = (k_num, (height-k_size+1)//stride, (width-k_size+1)//stride)
		self.stride = stride

	def forward(self, x):
		self.input = img2col(x, self.k_size, self.stride)
		out = self.act_func(self.input.dot(self.w)+self.b)
		out = out.reshape(self.out_shape[1], self.out_shape[2], x.shape[0], self.out_shape[0])
		return out.transpose(2, 3, 0, 1)

	def gradient(self, grad_act, act):
		batch_size = grad_act.shape[0]
		grad_out = self.dact_func(grad_act, act).transpose(2,3,0,1).reshape([-1, self.out_shape[0]])
		self.grad_w = self.input.T.dot(grad_out) / batch_size
		self.grad_b = np.ones((1, grad_out.shape[0])).dot(grad_out) / batch_size
		self.input = None
		return np.array(col2img(grad_out.dot(self.w.T), self.in_shape, self.out_shape, self.k_size, self.stride))

class MaxPooling(Layer):
	def __init__(self, in_shape, k_size, stride=None):
		super(MaxPooling, self).__init__(has_param=False)
		self.in_shape = in_shape
		channel, height, width = in_shape
		self.k_size = k_size
		self.stride = k_size if stride is None else stride 
		self.out_shape = [channel, height//self.stride, width//self.stride]

	def gradient(self, grad_out):
		grad_out = np.repeat(grad_out, self.k_size, axis=2)
		grad_out = np.repeat(grad_out, self.k_size, axis=3)
		return np.multiply(self.mask, grad_out)

	def forward(self, x):
		col = img2col(x.reshape(-1,1,self.in_shape[1],self.in_shape[2]), k_size=self.k_size, stride=self.stride)
		max_idx = np.argmax(col, axis=1)
		col_mask = np.zeros(col.shape)
		col_mask[range(col.shape[0]),max_idx] = 1
		col_mask = col_mask.reshape(self.out_shape[1]* self.out_shape[2]* x.shape[0], self.in_shape[0]*self.k_size*self.k_size)
		self.mask = col2img(col_mask, self.in_shape, self.out_shape, self.k_size, self.stride)
		out = col[range(col.shape[0]),max_idx].reshape(self.out_shape[1],self.out_shape[2],x.shape[0], self.in_shape[0])
		return out.transpose(2, 3, 0, 1)

class Softmax(Layer):
	def __init__(self, w_size):
		super(Softmax, self).__init__(has_param=False)

	def forward(self, x):
		return self.predict(x)

	def loss(self, out, y):
		eps = 1e-8
		return -(np.multiply(y, np.log(out+eps))).mean()

	def predict(self, x):
		eps = 1e-8
		out = np.exp(x - np.max(x, axis=1).reshape([-1, 1]))
		return out / (np.sum(out, axis=1).reshape([-1, 1]) + eps)

	def gradient(self, out, y):
		return out - y

class FullyConnect(Layer):
	def __init__(self, in_shape, out_dim, act_type):
		super(FullyConnect, self).__init__(has_param=True)
		self.act_func = self.act_funcs[act_type]
		self.dact_func = self.dact_funcs[act_type]
		self.in_shape = np.array(in_shape)
		self.w = np.random.randn(self.in_shape.prod(), out_dim)
		self.b = np.random.randn(1, out_dim)
		self.mom_w = np.zeros_like(self.w)
		self.cache_w = np.zeros_like(self.w)
		self.mom_b = np.zeros_like(self.b)
		self.cache_b = np.zeros_like(self.b)

	def forward(self, x):
		self.input = x.reshape([x.shape[0],-1])
		return self.act_func(self.input.dot(self.w)+self.b)

	def gradient(self, grad_act, act):
		grad_act=grad_act.reshape([grad_act.shape[0], grad_act.shape[1]])
		batch_size = grad_act.shape[0]
		grad_out = self.dact_func(grad_act, act)
		self.grad_w = self.input.T.dot(grad_out)
		self.grad_b = np.ones((1, batch_size)).dot(grad_out)
		self.grad_w /= batch_size
		self.grad_b /= batch_size
		self.input = None
		in_shape = self.in_shape.copy()
		return grad_out.dot(self.w.T).reshape(np.insert(in_shape, 0, -1))