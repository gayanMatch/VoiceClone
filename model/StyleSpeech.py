import os
import json

import torch
import torch.nn as nn
import torch.nn.functional as F

from .modules import (
    MelStyleEncoder,
    PhonemeEncoder,
    MelDecoder, 
    VarianceAdaptor,
    PhonemeDiscriminator,
    StyleDiscriminator,
)
from utils.tools import get_mask_from_lengths


class StyleSpeech(nn.Module):
    """ StyleSpeech """

    def __init__(self, preprocess_config, model_config):
        super(StyleSpeech, self).__init__()
        self.model_config = model_config

        self.mel_style_encoder = MelStyleEncoder(preprocess_config, model_config)
        self.phoneme_encoder = PhonemeEncoder(model_config)
        self.variance_adaptor = VarianceAdaptor(preprocess_config, model_config)
        self.mel_decoder = MelDecoder(model_config)
        self.phoneme_linear = nn.Linear(
            model_config["transformer"]["encoder_hidden"],
            model_config["transformer"]["encoder_hidden"],
        )
        self.mel_linear = nn.Linear(
            model_config["transformer"]["decoder_hidden"],
            preprocess_config["preprocessing"]["mel"]["n_mel_channels"],
        )
        self.phoneme_discriminator = PhonemeDiscriminator(preprocess_config, model_config)
        self.style_discriminator = StyleDiscriminator(preprocess_config, model_config)

    def forward(
        self,
        speakers,
        texts,
        src_lens,
        max_src_len,
        mels,
        mel_lens,
        max_mel_len,
        p_targets=None,
        e_targets=None,
        d_targets=None,
        p_control=1.0,
        e_control=1.0,
        d_control=1.0,
    ):
        src_masks = get_mask_from_lengths(src_lens, max_src_len)
        mel_masks = get_mask_from_lengths(mel_lens, max_mel_len)

        style_vector = self.mel_style_encoder(mels, mel_masks)

        output = self.phoneme_encoder(texts, style_vector, src_masks)
        output = self.phoneme_linear(output)

        (
            output,
            upsampled_text,
            p_predictions,
            e_predictions,
            log_d_predictions,
            d_rounded,
            mel_lens,
            mel_masks,
        ) = self.variance_adaptor(
            output,
            src_masks,
            mel_masks,
            max_mel_len,
            p_targets,
            e_targets,
            d_targets,
            p_control,
            e_control,
            d_control,
        )

        output, mel_masks = self.mel_decoder(output, style_vector, mel_masks)
        output = self.mel_linear(output)

        p_disc = self.phoneme_discriminator(upsampled_text, output, mel_masks)
        s_disc, style_logit = self.style_discriminator(speakers, style_vector, output, mel_masks)
        print(p_disc.shape, s_disc.shape, style_logit.shape)
        exit(0)

        return (
            output,
            p_predictions,
            e_predictions,
            log_d_predictions,
            d_rounded,
            src_masks,
            mel_masks,
            src_lens,
            mel_lens,
        )