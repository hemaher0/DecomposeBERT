import torch
from utils.model_utils.modular_layers import get_extended_attention_mask


class ConcernIdentificationBert:
    def __init__(self):
        self.positive_sample = True
        self.is_sparse = False
        self.a = 0
        self.b = 0
        self.c = 0
        self.d = 0
        self.e = 0
        self.f = 0

    def positive_hook(self, module, output):
        """
        Positive hook
        Attributes:
            module (Layer): custom layer
            output (torch.Tensor): output tensor of the original layer
        """
        # Get the shapes and original parameters (weights and biases) of the layer
        current_weight, current_bias = module.weight, module.bias   # updating parameters
        original_weight, original_bias = module.get_parameters()
        positive_output_mask = output[0] > 0
        negative_output_mask = output[0] < 0
        positive_weight_mask = original_weight > 0
        negative_weight_mask = original_weight < 0

        if torch.sum(current_weight != 0) < module.shape[0] * module.shape[1] * 0.1:
            self.is_sparse = True
        else:
            self.is_sparse = False

        if self.is_sparse:
            extended_mask = negative_output_mask.unsqueeze(1).expand(-1, module.shape[1])
            k = positive_weight_mask
            temp = torch.logical_and(extended_mask, k)
            not_all_zeros = temp.any(dim=1)
            current_weight[temp] = original_weight[temp]
            current_bias[not_all_zeros] = original_bias[not_all_zeros]

        else:
            extended_mask = positive_output_mask.unsqueeze(1).expand(-1, module.shape[1])
            k = negative_weight_mask
            temp = torch.logical_or(extended_mask, k)
            current_weight[temp] = 0
            all_zeros = ~temp.any(dim=1)
            current_bias[all_zeros] = 0

        module.set_parameters(current_weight, current_bias)

    def negative_hook(self, module, output):
        # Get the shapes and original parameters (weights and biases) of the module
        current_weight, current_bias = module.weight, module.bias
        original_weight, original_bias = module.get_parameters()
        negative_output_mask = output[0] < 0
        positive_output_mask = output[0] > 0

        positive_weight_mask = original_weight > 0
        negative_weight_mask = original_weight < 0

        if torch.sum(current_weight != 0) < module.shape[0] * module.shape[1] * 0.1:
            self.is_sparse = True
        else:
            self.is_sparse = False

        if self.is_sparse:
            if self.a == 0:
                extended_mask = positive_output_mask.unsqueeze(1).expand(-1, module.shape[1])
            else:
                extended_mask = negative_output_mask.unsqueeze(1).expand(-1, module.shape[1])

            if self.b == 0:
                k = negative_weight_mask
            else:
                k = positive_weight_mask

            if self.c == 0:
                temp = torch.logical_and(extended_mask, k)
            else:
                temp = torch.logical_or(extended_mask, k)
            not_all_zeros = temp.any(dim=1)
            current_weight[temp] = original_weight[temp]
            current_bias[not_all_zeros] = original_bias[not_all_zeros]

        else:
            if self.d == 0:
                extended_mask = positive_output_mask.unsqueeze(1).expand(-1, module.shape[1])
            else:
                extended_mask = negative_output_mask.unsqueeze(1).expand(-1, module.shape[1])

            if self.e == 0:
                k = positive_weight_mask
            else:
                k = negative_weight_mask

            if self.f == 0:
                temp = torch.logical_and(extended_mask, k)
            else:
                temp = torch.logical_or(extended_mask, k)
            current_weight[temp] = 0
            all_zeros = ~temp.any(dim=1)
            current_bias[all_zeros] = 0

        module.set_parameters(current_weight, current_bias)

    def propagate(self, module, input_tensor, attention_mask, positive_sample=True):
        # propagate input tensor to the module
        self.positive_sample = positive_sample
        output_tensor = self.propagate_embeddings(module.embeddings, input_tensor)
        output_tensor = self.propagate_encoder(
            module.encoder, output_tensor, attention_mask
        )
        output_tensor = self.propagate_pooler(module.pooler, output_tensor)
        output_tensor = module.dropout(output_tensor)
        output_tensor = self.propagate_classifier(module.classifier, output_tensor)
        return output_tensor

    def propagate_embeddings(self, module, input_tensor):
        output_tensor = module(input_tensor)
        return output_tensor

    def propagate_encoder(self, module, input_tensor, attention_mask):
        attention_mask = get_extended_attention_mask(attention_mask)
        maxi = len(module.encoder_blocks) - 1
        for i, encoder_block in enumerate(module.encoder_blocks):
            block_outputs = self.propagate_encoder_block(
                encoder_block, input_tensor, attention_mask, i, maxi, None
            )
            input_tensor = block_outputs[0]
        return input_tensor

    def propagate_encoder_block(
        self, module, input_tensor, attention_mask, i, maxi, head_mask=None
    ):
        def ff1_hook(module, input, output):
            if self.positive_sample:
                original_output = module.layer(input[0])
                self.positive_hook(module, original_output[:, 0, :])
            else:
                original_outputs = module.layer(input[0])
                self.negative_hook(module, original_outputs[:, 0, :])

        attn_outputs = module.attention(input_tensor, attention_mask, head_mask)
        self.attn_probs = module.attention.self_attention.attention_probs
        handle = module.feed_forward1.dense.register_forward_hook(ff1_hook)
        intermediate_output = module.feed_forward1(attn_outputs)
        handle.remove()
        handle = module.feed_forward2.dense.register_forward_hook(ff1_hook)
        layer_output = module.feed_forward2(intermediate_output, attn_outputs)
        handle.remove()
        return (layer_output,)

    def propagate_attention_module(
        self, module, input_tensor, attention_mask, head_mask
    ):
        # handle = module.self_attention.register_forward_hook(attention_hook)
        self_outputs = module.self_attention(input_tensor, attention_mask, head_mask)
        # handle.remove()
        # handle = module.output.register_forward_hook(output_hook)
        attention_output = module.output(self_outputs[0], input_tensor)
        # handle.remove()
        return attention_output

    def propagate_pooler(self, module, input_tensor):
        first_token_tensor = input_tensor[:, 0]
        def pooler_hook(module, input, output):
            # Get the original output from model
            if self.positive_sample:
                original_outputs = module.layer(input[0])
                self.positive_hook(module, original_outputs)
            else:
                original_outputs = module.layer(input[0])
                self.negative_hook(module, original_outputs)

        handle = module.dense.register_forward_hook(pooler_hook)
        output_tensor = module.dense(first_token_tensor)
        handle.remove()
        output_tensor = module.activation(output_tensor)
        return output_tensor

    def propagate_classifier(self, module, input_tensor):
        def classifier_hook(module, input, output):
            if self.positive_sample:
                original_outputs = module.layer(input[0])
                self.positive_hook(module, original_outputs)
            else:
                original_outputs = module.layer(input[0])
                self.negative_hook(module, original_outputs)
        handle = module.register_forward_hook(classifier_hook)
        output_tensor = module(input_tensor)
        handle.remove()
        return output_tensor


    def remove_broken_weights(self, module):
        pass

    def recover_broken_weights(self, module):
        pass
