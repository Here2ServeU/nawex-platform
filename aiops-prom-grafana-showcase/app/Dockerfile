FROM node:18-alpine
WORKDIR /usr/src/app
COPY package*.json ./
# Changed to 'install' to fix build error
RUN npm install
COPY . .
EXPOSE 3000
CMD ["node", "server.js"]
