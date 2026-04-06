/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, useState } from "@odoo/owl";

export class AudioRecorderField extends Component {
  setup() {
    this.state = useState({
      isRecording: false,
      audioUrl: null,
      errorMsg: null,
    });
    this.mediaRecorder = null;
    this.audioChunks = [];

    if (this.props.record.data[this.props.name]) {
      this.state.audioUrl = `data:audio/webm;base64,${this.props.record.data[this.props.name]}`;
    }
  }

  async toggleRecording() {
    if (this.state.isRecording) {
      this.stopRecording();
    } else {
      await this.startRecording();
    }
  }

  async startRecording() {
    this.state.errorMsg = null;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.mediaRecorder = new MediaRecorder(stream);
      this.audioChunks = [];

      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.audioChunks.push(event.data);
        }
      };

      this.mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(this.audioChunks, { type: "audio/webm" });

        const reader = new FileReader();
        reader.readAsDataURL(audioBlob);
        reader.onloadend = () => {
          const base64data = reader.result;
          const b64 = base64data.split(",")[1];
          this.props.record.update({ [this.props.name]: b64 });
        };

        this.state.audioUrl = URL.createObjectURL(audioBlob);
      };

      this.mediaRecorder.start();
      this.state.isRecording = true;
    } catch (err) {
      console.error("Error al acceder al micrófono: ", err);
      this.state.errorMsg = "Permiso de micrófono denegado.";
    }
  }

  stopRecording() {
    if (this.mediaRecorder && this.state.isRecording) {
      this.mediaRecorder.stop();
      this.mediaRecorder.stream.getTracks().forEach((track) => track.stop());
      this.state.isRecording = false;
    }
  }

  // NUEVA FUNCIÓN: Descarta el audio y vacía el campo en Odoo
  clearRecording() {
    this.state.audioUrl = null;
    this.audioChunks = [];
    this.props.record.update({ [this.props.name]: false });
  }
}

AudioRecorderField.template = "mi_modulo_prueba.AudioRecorderField";
AudioRecorderField.props = {
  ...standardFieldProps,
};

export const audioRecorderFieldDefinition = {
  component: AudioRecorderField,
  supportedTypes: ["binary"],
};

registry.category("fields").add("audio_recorder", audioRecorderFieldDefinition);
