FROM node:24.14.1-bookworm-slim
RUN npm install --global npm@11.20.0 --ignore-scripts --no-audit --no-fund
WORKDIR /workspace
COPY package.json package-lock.json ./
COPY frontend/package.json ./frontend/package.json
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY frontend/ ./frontend/
RUN npm run build --workspace frontend
RUN chown -R node:node /workspace
USER node
EXPOSE 5173
CMD ["npm", "run", "dev", "--workspace", "frontend"]
